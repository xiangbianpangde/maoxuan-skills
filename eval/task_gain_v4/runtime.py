from __future__ import annotations
import copy, hashlib, json, random, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
EVAL_DIR=ROOT/"eval"
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0,str(EVAL_DIR))

import run_router_benchmark as rb
import run_heldout_benchmark as hb
from task_gain import runtime as legacy
from task_gain_v3 import runtime as v3

VARIANTS=["vanilla","generic-planner","method-planner"]

def git_blob_sha(path:Path)->str:
    data=path.read_bytes()
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()

def load_suite():
    d=ROOT/"eval/task_gain_v4"
    freeze=json.loads((d/"TASK_GAIN_V4_FREEZE.json").read_text(encoding="utf-8"))
    paths=[
        (d/"tasks-v4.jsonl","tasks_git_blob"),
        (d/"rubric-v4.json","rubric_git_blob"),
        (ROOT/"skills/runtime/PLANNER_RELIABILITY_V4.json","planner_reliability_policy_git_blob"),
        (ROOT/"skills/runtime/PLANNER_CONTRACT.json","planner_contract_git_blob"),
        (ROOT/"skills/runtime/RUNTIME_CARDS.json","runtime_cards_git_blob"),
    ]
    for p,k in paths:
        got=git_blob_sha(p)
        if got!=freeze[k]:
            raise ValueError(f"{p} git-blob mismatch: {got} != {freeze[k]}")
    rubric=json.loads((d/"rubric-v4.json").read_text(encoding="utf-8"))
    tasks=[json.loads(x) for x in (d/"tasks-v4.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    for t in tasks:
        t["weights"]=dict(rubric["weights"])
    if len(tasks)!=freeze["cases_total"] or len({x["id"] for x in tasks})!=len(tasks):
        raise ValueError("task count or uniqueness mismatch")
    return (
        tasks,
        rubric,
        freeze,
        json.loads((ROOT/"skills/runtime/PLANNER_CONTRACT.json").read_text(encoding="utf-8")),
        json.loads((ROOT/"skills/runtime/PLANNER_RELIABILITY_V4.json").read_text(encoding="utf-8")),
    )

def load_cards():
    return v3.load_cards()

def normalize_plan(plan:dict, contract:dict, policy:dict):
    if not isinstance(plan,dict):
        return plan,[]
    p=copy.deepcopy(plan)
    changes=[]
    list_fields=policy["normalization"]["list_fields"]
    for k in list_fields:
        if k not in p and k in {"facts","unknowns","dependencies","assumptions","answer_focus"}:
            p[k]=[]; changes.append(f"{k}:missing->[]")
        elif isinstance(p.get(k),str):
            p[k]=[p[k]]; changes.append(f"{k}:string->list")
    if isinstance(p.get("actions"),dict):
        p["actions"]=[p["actions"]]; changes.append("actions:dict->list")
    for k in list_fields:
        if isinstance(p.get(k),list):
            cleaned=[]
            for x in p[k]:
                if isinstance(x,str):
                    y=x.strip()
                    if y:
                        cleaned.append(y)
                    elif x!=y:
                        changes.append(f"{k}:drop-empty")
                else:
                    cleaned.append(x)
            if cleaned!=p[k]:
                p[k]=cleaned
    bounds=policy["normalization"]["bounded_truncation"]
    c=contract["constraints"]
    for field,bound_key in bounds.items():
        if isinstance(p.get(field),list):
            limit=int(c[bound_key])
            if len(p[field])>limit:
                p[field]=p[field][:limit]
                changes.append(f"{field}:truncate->{limit}")
    return p,changes

def parse_normalize_validate(text:str,contract:dict,policy:dict):
    visible,stripped=v3.sanitize_visible(text)
    try:
        raw=rb.parse_json_object(visible)
    except Exception as e:
        return None,[f"parse: {type(e).__name__}: {e}"],[],stripped
    plan,changes=normalize_plan(raw,contract,policy)
    errs=v3.validate_plan(plan,contract)
    return plan,errs,changes,stripped

def call_planner(case:dict,route:dict,cards:dict,contract:dict,policy:dict,args,with_methods:bool):
    selected=v3.selected_cards(route,cards,contract) if with_methods else []
    method_context="\n\n".join(v3.render_card(c) for c in selected)
    user_obj={"task":case["prompt"],"reference_requirements":case["reference_requirements"],"hardness_features":case.get("hardness_features",[])}
    user=json.dumps(user_obj,ensure_ascii=False)
    if method_context:
        user+="\n\nINTERNAL METHOD CARDS:\n"+method_context
    sysmsg=v3.planner_system(with_methods,contract)
    payloads=[]; repaired=False; all_changes=[]; stripped_total=0
    t=time.perf_counter()
    try:
        text,p=rb.post_chat(args.base_url,args.api_key,args.model,sysmsg,user,args.timeout,not args.no_response_format)
        payloads.append(p)
        plan,errs,changes,stripped=parse_normalize_validate(text,contract,policy)
        all_changes.extend(changes); stripped_total+=stripped
        if errs:
            repaired=True
            repair_user=user+"\n\nPrevious planner output remained invalid after deterministic normalization: "+json.dumps(errs,ensure_ascii=False)+". Return complete corrected JSON only."
            text,p=rb.post_chat(args.base_url,args.api_key,args.model,sysmsg,repair_user,args.timeout,not args.no_response_format)
            payloads.append(p)
            plan,errs,changes,stripped=parse_normalize_validate(text,contract,policy)
            all_changes.extend(changes); stripped_total+=stripped
        if errs:
            raise ValueError("; ".join(errs))
        return {
            "plan":plan,"selected_slugs":[c["slug"] for c in selected],
            "usage":rb.usage_total(payloads),"latency_s":round(time.perf_counter()-t,3),
            "repair_attempted":repaired,"normalizations":all_changes,
            "reasoning_stripped_chars":stripped_total,
            "planner_context_chars":len(sysmsg)+len(user),"error":None
        }
    except Exception as e:
        return {
            "plan":None,"selected_slugs":[c["slug"] for c in selected],
            "usage":rb.usage_total(payloads),"latency_s":round(time.perf_counter()-t,3),
            "repair_attempted":repaired,"normalizations":all_changes,
            "reasoning_stripped_chars":stripped_total,
            "planner_context_chars":len(sysmsg)+len(user),
            "error":f"{type(e).__name__}: {e}"
        }

def answer_one(case:dict,variant:str,route:dict,schema:dict,cards:dict,contract:dict,policy:dict,args):
    if variant=="vanilla":
        ans=v3.direct_answer(case,"vanilla",route,schema,cards,args)
        ans["fallback_used"]=False
        return ans
    with_methods=variant=="method-planner"
    planner=call_planner(case,route,cards,contract,policy,args,with_methods)
    if planner["error"] or not planner["plan"]:
        final=v3.direct_answer(case,"vanilla",route,schema,cards,args)
        final["planner"]=planner
        final["fallback_used"]=True
        final["fallback_reason"]=planner["error"]
        final["latency_s"]=round(final["latency_s"]+planner["latency_s"],3)
        final["reasoning_stripped_chars"]+=planner["reasoning_stripped_chars"]
        return final
    final=v3.call_executor(case,planner["plan"],contract,args)
    final["planner"]=planner
    final["fallback_used"]=False
    final["latency_s"]=round(final["latency_s"]+planner["latency_s"],3)
    final["reasoning_stripped_chars"]+=planner["reasoning_stripped_chars"]
    return final

def label_map(task_id:str)->dict:
    vs=list(VARIANTS)
    random.Random(int(hashlib.sha256(("v4:"+task_id).encode()).hexdigest()[:16],16)).shuffle(vs)
    return dict(zip("ABC",vs))

def judge_system(rubric:dict)->str:
    dims="\n".join(f"- {k}: {v}" for k,v in rubric["dimensions"].items())
    anc="\n".join(f"- {k}: {v}" for k,v in rubric["anchors"].items())
    row='{"factual_correctness":0,"method_fit":0,"analysis_structure":0,"actionability":0,"evidence_fidelity":0,"boundary_compliance":0,"overall_utility":0}'
    policy="\n".join("- "+x for x in rubric.get("judge_policy",[]))
    return f"""You are a blinded evaluator. Judge only the sanitized visible final answer; never request or reward hidden chain-of-thought.
Do not infer whether an answer used a planner or Method Cards.
Judge policy:
{policy}
Dimensions:
{dims}
Integer score anchors 0-4:
{anc}
Return JSON only:
{{"scores":{{"A":{row},"B":{row},"C":{row}}},"best_labels":["A"],"notes":{{"A":"","B":"","C":""}}}}"""

def validate_judge(parsed:dict,rubric:dict):
    out={}; errs=[]; dims=set(rubric["dimensions"])
    for lab in "ABC":
        row=(parsed.get("scores") or {}).get(lab)
        if not isinstance(row,dict):
            errs.append(f"missing {lab}"); continue
        clean={}
        for d in dims:
            v=row.get(d)
            if not isinstance(v,(int,float)) or not 0<=v<=4:
                errs.append(f"invalid {lab}.{d}")
            else:
                clean[d]=float(v)
        out[lab]=clean
    return out,errs

def judge_one(case:dict,answers:dict,rubric:dict,args):
    mapping=label_map(case["id"])
    anon={lab:answers[v]["text"] for lab,v in mapping.items()}
    prompt=json.dumps({
        "task":case["prompt"],"reference_requirements":case["reference_requirements"],
        "hardness_features":case["hardness_features"],"dimension_weights":case["weights"],"answers":anon
    },ensure_ascii=False)
    sysmsg=judge_system(rubric); payloads=[]; repaired=False; t=time.perf_counter()
    model=args.judge_model or args.model
    try:
        text,p=rb.post_chat(args.base_url,args.api_key,model,sysmsg,prompt,args.timeout,not args.no_response_format)
        payloads.append(p); visible,_=v3.sanitize_visible(text); parsed=rb.parse_json_object(visible)
        scores,errs=validate_judge(parsed,rubric)
        if errs:
            repaired=True
            rp=prompt+"\nPrevious judge JSON invalid: "+json.dumps(errs,ensure_ascii=False)+". Return complete corrected JSON only."
            text,p=rb.post_chat(args.base_url,args.api_key,model,sysmsg,rp,args.timeout,not args.no_response_format)
            payloads.append(p); visible,_=v3.sanitize_visible(text); parsed=rb.parse_json_object(visible)
            scores,errs=validate_judge(parsed,rubric)
        if errs:
            raise ValueError("; ".join(errs))
        return {"label_map":mapping,"scores":scores,"best_labels":parsed.get("best_labels") or [],
                "notes":parsed.get("notes") or {},"judge_model":model,"usage":rb.usage_total(payloads),
                "repair_attempted":repaired,"latency_s":round(time.perf_counter()-t,3),"error":None}
    except Exception as e:
        return {"label_map":mapping,"scores":{},"best_labels":[],"notes":{},"judge_model":model,
                "usage":rb.usage_total(payloads),"repair_attempted":repaired,
                "latency_s":round(time.perf_counter()-t,3),"error":f"{type(e).__name__}: {e}"}
