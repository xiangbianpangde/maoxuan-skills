from __future__ import annotations
import hashlib, json, random, re, statistics, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = ROOT / "eval"
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))
import run_router_benchmark as rb
import run_heldout_benchmark as hb

VARIANTS = ["vanilla","retrieval-only","atomic","framework-atomic","full-system"]
SOURCE_RE = re.compile(r"MX-V\d{2}-A\d{3}-P\d{4}")

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_suite():
    d=ROOT/"eval/task_gain"
    freeze=json.loads((d/"TASK_GAIN_FREEZE.json").read_text(encoding="utf-8"))
    tasks_p=d/"tasks-v1.jsonl"; rubric_p=d/"rubric-v1.json"
    if sha256(tasks_p)!=freeze["tasks_sha256"]: raise ValueError("tasks hash mismatch")
    if sha256(rubric_p)!=freeze["rubric_sha256"]: raise ValueError("rubric hash mismatch")
    tasks=[json.loads(x) for x in tasks_p.read_text(encoding="utf-8").splitlines() if x.strip()]
    if len(tasks)!=freeze["cases_total"]: raise ValueError("task count mismatch")
    if len({x["id"] for x in tasks})!=len(tasks): raise ValueError("duplicate task id")
    return tasks,json.loads(rubric_p.read_text(encoding="utf-8")),freeze

def ensure_index():
    cfg=json.loads((ROOT/"retrieval/config.example.json").read_text(encoding="utf-8"))
    if not (ROOT/cfg["database"]).exists():
        subprocess.run([sys.executable,str(ROOT/"retrieval/build_index.py")],cwd=ROOT,check=True)

def retrieve(case,limit=8):
    if not case.get("needs_retrieval"): return []
    ensure_index()
    p=subprocess.run([sys.executable,str(ROOT/"retrieval/search.py"),"show",case["source_title"]],
                     cwd=ROOT,capture_output=True,text=True,check=True)
    rows=json.loads(p.stdout); kws=case.get("source_keywords",[])
    def sc(r): return sum(r.get("text","").count(k) for k in kws)
    ranked=sorted(rows,key=lambda r:(sc(r),-int(r.get("paragraph") or 0)),reverse=True)
    pos=[r for r in ranked if sc(r)>0]; out=pos[:limit]; seen={r["source_id"] for r in out}
    for r in ranked:
        if len(out)>=limit: break
        if r["source_id"] not in seen: out.append(r); seen.add(r["source_id"])
    return out

def source_context(rows):
    return "\n\n".join(f"[{r['source_id']}] {r['path']} ¶{r['paragraph']}\n{r['text']}" for r in rows)

def route_one(case,args,schema,system):
    payloads=[]; t=time.perf_counter()
    try:
        pred,corr,errs,repaired,meta=rb._call_and_normalize(
            case["prompt"],args,system,lambda raw: rb.normalize_final(raw,schema),payloads)
        return {"prediction":pred,"corrections":corr,"validation_errors":errs,
                "repair_attempted":repaired,"raw":meta["raw"],"usage":rb.usage_total(payloads),
                "latency_s":round(time.perf_counter()-t,3),"error":None}
    except Exception as e:
        return {"prediction":{"route":"direct","framework":None,"atomic_skills":[],"composite":None,"components":[]},
                "corrections":[],"validation_errors":[str(e)],"repair_attempted":False,"raw":None,
                "usage":rb.usage_total(payloads),"latency_s":round(time.perf_counter()-t,3),
                "error":f"{type(e).__name__}: {e}"}

def atomic_context(route,schema):
    chunks=[]
    for slug in route.get("atomic_skills") or []:
        meta=schema["skills"].get(slug); p=ROOT/meta["vendor_path"] if meta else None
        if p and p.exists(): chunks.append(f"[ATOMIC {slug}]\n"+p.read_text(encoding="utf-8",errors="replace")[:10000])
    return "\n\n".join(chunks)

def framework_context(route,schema):
    fid=route.get("framework")
    if not fid or fid not in schema["frameworks"]: return ""
    f=schema["frameworks"][fid]
    return f"[FRAMEWORK {fid}] {f.get('name','')}\nPurpose: {f.get('purpose','')}\nAtomic members: {', '.join(f.get('atomic_skills') or [])}"

def composite_context(route):
    cid=route.get("composite")
    if not cid: return ""
    p=ROOT/"skills/composite"/cid/"SKILL.md"
    return p.read_text(encoding="utf-8",errors="replace")[:12000] if p.exists() else ""

def base_system():
    return """Answer the Chinese task concisely but sufficiently (normally <=900 Chinese characters).
Do not expose hidden chain-of-thought; show only conclusions, observable structure, steps, checks and decision criteria.
Do not role-play as Mao or any political figure. Do not transform historical or military-origin methods into violence, coercion, political persuasion, electoral strategy or voter mobilization.
Modern transfer is limited to non-violent engineering, research, product, project management, education, organizational learning and lawful business competition.
Never invent local Source IDs or claim local-corpus support unless excerpts are provided."""

def variant_system(v,case,route,schema,rows):
    base=base_system()
    if v=="vanilla": return base+"\nNo project-specific corpus or methodology context is available."
    if v=="retrieval-only":
        if not rows: return base+"\nNo project-specific corpus or methodology context is available."
        return base+f"\nUse only these local excerpts for source claims; cite exact Source IDs and admit insufficiency.\n[LOCAL SOURCE]\n{source_context(rows)}"
    atoms=atomic_context(route,schema)
    common=base+"""\nMethodology context below is an internal problem-solving aid, not authoritative historical source text.
Use it only if it improves the task. Do not mention routing internals or force terminology. Do not attribute modern abstractions to original text."""
    if v=="atomic": return common+f"\n[ATOMIC SKILLS]\n{atoms or '(none selected)'}"
    fw=framework_context(route,schema)
    if v=="framework-atomic": return common+f"\n{fw or '[FRAMEWORK] none'}\n[ATOMIC SKILLS]\n{atoms or '(none selected)'}"
    if v=="full-system":
        comp=composite_context(route); src=source_context(rows)
        return common+f"""\nKeep SOURCE (text), INTERPRETATION (abstraction), and TRANSFER (modern non-violent use) separate.
When local excerpts exist, historical claims must cite supplied Source IDs.
[FROZEN ROUTE] {json.dumps(route,ensure_ascii=False)}
{fw or '[FRAMEWORK] none'}
[ATOMIC SKILLS]
{atoms or '(none selected)'}
[COMPOSITE]
{comp or '(none selected)'}
[LOCAL SOURCE]
{src or '(none needed)'}"""
    raise ValueError(v)

def answer_one(case,v,route,schema,rows,args):
    sysmsg=variant_system(v,case,route,schema,rows); t=time.perf_counter()
    try:
        text,payload=rb.post_chat(args.base_url,args.api_key,args.model,sysmsg,case["prompt"],args.timeout,False)
        return {"text":text.strip(),"usage":payload.get("usage"),"latency_s":round(time.perf_counter()-t,3),
                "system_chars":len(sysmsg),"error":None}
    except Exception as e:
        return {"text":"","usage":None,"latency_s":round(time.perf_counter()-t,3),
                "system_chars":len(sysmsg),"error":f"{type(e).__name__}: {e}"}

def label_map(task_id):
    vs=list(VARIANTS); random.Random(int(hashlib.sha256(task_id.encode()).hexdigest()[:16],16)).shuffle(vs)
    return dict(zip("ABCDE",vs))

def judge_system(rubric):
    dims="\n".join(f"- {k}: {v}" for k,v in rubric["dimensions"].items())
    anc="\n".join(f"- {k}: {v}" for k,v in rubric["anchors"].items())
    row='{"factual_correctness":0,"method_fit":0,"analysis_structure":0,"actionability":0,"evidence_fidelity":0,"boundary_compliance":0,"overall_utility":0}'
    return f"""You are a blinded evaluator. Judge visible answer quality only; never request hidden chain-of-thought.
Do not reward Mao terminology, historical style, verbosity, citations or methodology names by themselves.
Reward correctness, problem-method fit, useful structure, executable decisions and evidence discipline.
For source tasks, fabricated/unsupported Source IDs sharply reduce evidence_fidelity. Irrelevant historical quotation gives no benefit.
Dimensions:
{dims}
Integer score anchors 0-4:
{anc}
Return JSON only:
{{"scores":{{"A":{row},"B":{row},"C":{row},"D":{row},"E":{row}}},"best_labels":["A"],"notes":{{"A":"","B":"","C":"","D":"","E":""}}}}"""

def _validate_judge(parsed,rubric):
    out={}; errs=[]; dims=set(rubric["dimensions"])
    for lab in "ABCDE":
        row=(parsed.get("scores") or {}).get(lab)
        if not isinstance(row,dict): errs.append(f"missing {lab}"); continue
        clean={}
        for d in dims:
            v=row.get(d)
            if not isinstance(v,(int,float)) or not 0<=v<=4: errs.append(f"invalid {lab}.{d}")
            else: clean[d]=float(v)
        out[lab]=clean
    return out,errs

def judge_one(case,answers,rubric,args):
    mapping=label_map(case["id"]); anon={lab:answers[v]["text"] for lab,v in mapping.items()}
    prompt=json.dumps({"task":case["prompt"],"reference_requirements":case["reference_requirements"],
                       "dimension_weights":case["weights"],"answers":anon},ensure_ascii=False)
    sysmsg=judge_system(rubric); payloads=[]; t=time.perf_counter(); model=args.judge_model or args.model
    repaired=False
    try:
        text,p=rb.post_chat(args.base_url,args.api_key,model,sysmsg,prompt,args.timeout,not args.no_response_format)
        payloads.append(p); parsed=rb.parse_json_object(text); scores,errs=_validate_judge(parsed,rubric)
        if errs:
            repaired=True
            rp=prompt+"\nPrevious judge JSON invalid: "+json.dumps(errs,ensure_ascii=False)+". Return complete corrected JSON only."
            text,p=rb.post_chat(args.base_url,args.api_key,model,sysmsg,rp,args.timeout,not args.no_response_format)
            payloads.append(p); parsed=rb.parse_json_object(text); scores,errs=_validate_judge(parsed,rubric)
        if errs: raise ValueError("; ".join(errs))
        return {"label_map":mapping,"scores":scores,"best_labels":parsed.get("best_labels") or [],
                "notes":parsed.get("notes") or {},"judge_model":model,"usage":rb.usage_total(payloads),
                "repair_attempted":repaired,"latency_s":round(time.perf_counter()-t,3),"error":None}
    except Exception as e:
        return {"label_map":mapping,"scores":{},"best_labels":[],"notes":{},"judge_model":model,
                "usage":rb.usage_total(payloads),"repair_attempted":repaired,
                "latency_s":round(time.perf_counter()-t,3),"error":f"{type(e).__name__}: {e}"}

def weighted(case,scores):
    den=sum(float(w) for w in case["weights"].values() if float(w)>0)
    if not den: return None
    num=0
    for d,w in case["weights"].items():
        w=float(w)
        if w<=0: continue
        if d not in scores: return None
        num+=w*scores[d]
    return round(100*num/(4*den),3)

def citation_stats(text,valid_ids):
    cited=list(dict.fromkeys(SOURCE_RE.findall(text or ""))); valid=[x for x in cited if x in valid_ids]
    return {"count":len(cited),"valid_count":len(valid),"precision":round(len(valid)/len(cited),4) if cited else None,
            "has_valid_citation":bool(valid),"citations":cited}

def bootstrap(records,a,b,reps=2000):
    diffs=[r["variant_scores"][a]-r["variant_scores"][b] for r in records
           if r["variant_scores"].get(a) is not None and r["variant_scores"].get(b) is not None]
    if not diffs: return None
    rng=random.Random(20260927+sum(map(ord,a+b))); boots=[]; n=len(diffs)
    for _ in range(reps): boots.append(statistics.fmean(diffs[rng.randrange(n)] for __ in range(n)))
    boots.sort()
    return {"mean_diff_points":round(statistics.fmean(diffs),3),
            "ci95":[round(boots[int(.025*(reps-1))],3),round(boots[int(.975*(reps-1))],3)],"n":n}

def tokens(items):
    return sum(int((x.get("usage") or {}).get("total_tokens") or 0) for x in items)
