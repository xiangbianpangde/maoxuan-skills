from __future__ import annotations
import hashlib, json, random, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
EVAL_DIR=ROOT/"eval"
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0,str(EVAL_DIR))

import run_router_benchmark as rb
import run_heldout_benchmark as hb
from task_gain import runtime as legacy

VARIANTS=["vanilla","retrieval-only","legacy-raw","compact-atomic","full-v2"]

def sha256(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def git_blob_sha(path:Path)->str:
    data=path.read_bytes()
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()

def load_suite():
    d=ROOT/"eval/task_gain_v2"
    freeze=json.loads((d/"TASK_GAIN_V2_FREEZE.json").read_text(encoding="utf-8"))
    tp=d/"tasks-v2.jsonl"; rp=d/"rubric-v2.json"
    cp=ROOT/"skills/runtime/RUNTIME_CARDS.json"; xp=ROOT/"skills/runtime/COMPOSITE_CARDS.json"
    checks=[(tp,"tasks_git_blob"),(rp,"rubric_git_blob"),(cp,"runtime_cards_git_blob"),(xp,"composite_cards_git_blob")]
    for p,k in checks:
        got=git_blob_sha(p)
        if got!=freeze[k]: raise ValueError(f"{p} git-blob mismatch: {got} != {freeze[k]}")
    tasks=[json.loads(x) for x in tp.read_text(encoding="utf-8").splitlines() if x.strip()]
    if len(tasks)!=freeze["cases_total"]: raise ValueError("task count mismatch")
    if len({x["id"] for x in tasks})!=len(tasks): raise ValueError("duplicate task id")
    return tasks,json.loads(rp.read_text(encoding="utf-8")),freeze

def load_cards():
    doc=json.loads((ROOT/"skills/runtime/RUNTIME_CARDS.json").read_text(encoding="utf-8"))
    comps=json.loads((ROOT/"skills/runtime/COMPOSITE_CARDS.json").read_text(encoding="utf-8"))
    return {x["slug"]:x for x in doc["cards"]},{x["id"]:x for x in comps["cards"]}

def base_system():
    return """Answer the Chinese task directly, specifically and concisely (normally <=900 Chinese characters).
Do not expose hidden chain-of-thought; show only conclusions, observable structure, steps, checks, thresholds and decision criteria.
Do not role-play as a political or historical figure. Do not use current political persuasion, elections, voter mobilization, violence, coercion or evasion as application domains.
For technical tasks, preserve domain-specific variables, constraints, experiments, rollback/stop criteria and measurable acceptance conditions.
Never invent local Source IDs or claim local-corpus support unless excerpts are supplied."""

def render_card(c):
    return "\n".join([f"[METHOD {c['runtime_name']}]",f"Objective: {c['objective']}","Use when: "+"；".join(c["trigger"]),"Steps:",*[f"{i+1}. {s}" for i,s in enumerate(c["steps"])],"Checks: "+"；".join(c["checks"]),"Avoid: "+"；".join(c["avoid"])])

def compact_context(route,cards):
    chunks=[]
    for slug in (route.get("atomic_skills") or [])[:4]:
        c=cards.get(slug)
        if c: chunks.append(render_card(c))
    return "\n\n".join(chunks)

def framework_hint(route,schema):
    fid=route.get("framework"); f=schema["frameworks"].get(fid) if fid else None
    return f"[COORDINATION HINT] {f.get('purpose','')}" if f else ""

def composite_context(route,comps):
    cid=route.get("composite"); c=comps.get(cid) if cid else None
    if not c: return ""
    return "\n".join([f"[MULTI-STAGE WORKFLOW {c['runtime_name']}]",*[f"{i+1}. {s}" for i,s in enumerate(c["steps"])],f"Avoid: {c['avoid']}"])

def retrieval_context(rows):
    return "[LOCAL SOURCE]\n"+legacy.source_context(rows) if rows else ""

def variant_system(v,case,route,schema,rows,cards,comps):
    base=base_system()
    if v=="vanilla": return base+"\nNo project-specific corpus or methodology context is available."
    if v=="retrieval-only":
        if not rows: return base+"\nNo project-specific corpus or methodology context is available."
        return base+"\nUse only supplied local excerpts for historical/source claims; cite exact Source IDs and admit insufficiency.\n"+retrieval_context(rows)
    if v=="legacy-raw":
        raw=legacy.atomic_context(route,schema)
        return base+"\nThe following legacy methodology documents are internal problem-solving aids, not authoritative historical source text.\nUse them only if they materially improve the task; do not force their terminology into the answer.\n[LEGACY RAW SKILLS]\n"+(raw or "(none selected)")
    compact=compact_context(route,cards)
    if v=="compact-atomic":
        if not compact: return base+"\nNo compact method card is needed for this task."
        return base+"\nUse the compact method card(s) only as internal execution guidance. Do not name the cards unless the user asks.\nPreserve task-specific technical detail; the card must not replace domain reasoning.\n"+compact
    if v=="full-v2":
        r=route.get("route")
        if r=="source_lookup":
            if not rows: return base+"\nNo local evidence was retrieved; state that limitation."
            return base+"\nUse only supplied local excerpts for source claims; cite exact Source IDs.\n"+retrieval_context(rows)
        if r=="direct": return base+"\nNo project-specific method context is needed."
        parts=[base,"Use only the minimum supplied method guidance. Do not mention routing, card names, or methodology provenance unless asked. Preserve domain-specific detail."]
        hint=framework_hint(route,schema); comp=composite_context(route,comps)
        if hint: parts.append(hint)
        if compact: parts.append(compact)
        if r in {"composite_task","mixed"} and comp: parts.append(comp)
        if r=="mixed":
            if rows:
                parts.append("For source claims, cite exact supplied Source IDs and keep source evidence separate from modern transfer.")
                parts.append(retrieval_context(rows))
            else: parts.append("No local evidence was retrieved; do not invent source support.")
        return "\n\n".join(parts)
    raise ValueError(v)

def answer_one(case,v,route,schema,rows,cards,comps,args):
    sysmsg=variant_system(v,case,route,schema,rows,cards,comps); t=time.perf_counter()
    try:
        text,payload=rb.post_chat(args.base_url,args.api_key,args.model,sysmsg,case["prompt"],args.timeout,False)
        return {"text":text.strip(),"usage":payload.get("usage"),"latency_s":round(time.perf_counter()-t,3),"system_chars":len(sysmsg),"error":None}
    except Exception as e:
        return {"text":"","usage":None,"latency_s":round(time.perf_counter()-t,3),"system_chars":len(sysmsg),"error":f"{type(e).__name__}: {e}"}

def label_map(task_id):
    vs=list(VARIANTS); random.Random(int(hashlib.sha256(("v2:"+task_id).encode()).hexdigest()[:16],16)).shuffle(vs)
    return dict(zip("ABCDE",vs))

def judge_one(case,answers,rubric,args):
    mapping=label_map(case["id"]); anon={lab:answers[v]["text"] for lab,v in mapping.items()}
    prompt=json.dumps({"task":case["prompt"],"reference_requirements":case["reference_requirements"],"dimension_weights":case["weights"],"answers":anon},ensure_ascii=False)
    sysmsg=legacy.judge_system(rubric); payloads=[]; t=time.perf_counter(); model=args.judge_model or args.model; repaired=False
    try:
        text,p=rb.post_chat(args.base_url,args.api_key,model,sysmsg,prompt,args.timeout,not args.no_response_format)
        payloads.append(p); parsed=rb.parse_json_object(text); scores,errs=legacy._validate_judge(parsed,rubric)
        if errs:
            repaired=True; rp=prompt+"\nPrevious judge JSON invalid: "+json.dumps(errs,ensure_ascii=False)+". Return complete corrected JSON only."
            text,p=rb.post_chat(args.base_url,args.api_key,model,sysmsg,rp,args.timeout,not args.no_response_format)
            payloads.append(p); parsed=rb.parse_json_object(text); scores,errs=legacy._validate_judge(parsed,rubric)
        if errs: raise ValueError("; ".join(errs))
        return {"label_map":mapping,"scores":scores,"best_labels":parsed.get("best_labels") or [],"notes":parsed.get("notes") or {},"judge_model":model,"usage":rb.usage_total(payloads),"repair_attempted":repaired,"latency_s":round(time.perf_counter()-t,3),"error":None}
    except Exception as e:
        return {"label_map":mapping,"scores":{},"best_labels":[],"notes":{},"judge_model":model,"usage":rb.usage_total(payloads),"repair_attempted":repaired,"latency_s":round(time.perf_counter()-t,3),"error":f"{type(e).__name__}: {e}"}
