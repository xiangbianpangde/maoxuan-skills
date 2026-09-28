#!/usr/bin/env python3
from __future__ import annotations
import argparse, concurrent.futures, json, os, random, statistics
from pathlib import Path
from types import SimpleNamespace

from task_gain_v3 import runtime as tg
from task_gain import runtime as legacy

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval/results"

def usage_tokens(x):
    return int(((x or {}).get("usage") or {}).get("total_tokens") or 0)

def answer_executor_tokens(a):
    return usage_tokens(a)

def answer_planner_tokens(a):
    return usage_tokens(a.get("planner") or {})

def bootstrap(records, a, b, reps, seed=20260928):
    diffs=[]
    for r in records:
        x=r["variant_scores"].get(a); y=r["variant_scores"].get(b)
        if x is not None and y is not None: diffs.append(x-y)
    if not diffs: return None
    rng=random.Random(seed+sum(map(ord,a+b))); boots=[]; n=len(diffs)
    for _ in range(reps): boots.append(statistics.fmean(diffs[rng.randrange(n)] for __ in range(n)))
    boots.sort(); lo=boots[int(.025*(reps-1))]; hi=boots[int(.975*(reps-1))]
    return {"mean_diff_points":round(statistics.fmean(diffs),3),"ci95":[round(lo,3),round(hi,3)],"n":n}

def wtl(records,a,b):
    w=t=l=0
    for r in records:
        x=r["variant_scores"].get(a); y=r["variant_scores"].get(b)
        if x is None or y is None: continue
        d=round(x-y,9)
        if d>0: w+=1
        elif d<0: l+=1
        else: t+=1
    return {"wins":w,"ties":t,"losses":l}

def dim_means(records):
    by_variant={v:{} for v in tg.VARIANTS}; dims=set()
    for r in records:
        mapping=r["judge"]["label_map"]
        for lab,variant in mapping.items():
            ds=(r["judge"]["scores"] or {}).get(lab,{})
            dims.update(ds)
            for k,val in ds.items(): by_variant[variant].setdefault(k,[]).append(float(val))
    return {v:{d:round(statistics.fmean(vals),3) if vals else None for d in sorted(dims) for vals in [by_variant[v].get(d,[])]} for v in tg.VARIANTS}

def category_means(records):
    cats=sorted({r["category"] for r in records}); out={}
    for v in tg.VARIANTS:
        out[v]={}
        for c in cats:
            vals=[r["variant_scores"][v] for r in records if r["category"]==c and r["variant_scores"].get(v) is not None]
            out[v][c]=round(statistics.fmean(vals),3) if vals else None
    return out

def tag_diffs(records):
    tags=sorted({tag for r in records for tag in r.get("hardness_features",[]) }); out={}
    for tag in tags:
        rs=[r for r in records if tag in r.get("hardness_features",[])]
        def md(a,b):
            ds=[r["variant_scores"][a]-r["variant_scores"][b] for r in rs if r["variant_scores"].get(a) is not None and r["variant_scores"].get(b) is not None]
            return round(statistics.fmean(ds),3) if ds else None
        out[tag]={"n":len(rs),"method-planner_vs_vanilla":md("method-planner","vanilla"),"method-planner_vs_generic-planner":md("method-planner","generic-planner")}
    return out

def summarize(records,rubric,freeze,contract,args):
    means={}
    for v in tg.VARIANTS:
        vals=[r["variant_scores"][v] for r in records if r["variant_scores"].get(v) is not None]
        means[v]=round(statistics.fmean(vals),3) if vals else None
    reps=int(rubric["reporting"]["paired_bootstrap_reps"])
    comps={
      "method-planner_vs_vanilla":bootstrap(records,"method-planner","vanilla",reps),
      "method-planner_vs_generic-planner":bootstrap(records,"method-planner","generic-planner",reps),
      "generic-planner_vs_vanilla":bootstrap(records,"generic-planner","vanilla",reps),
      "method-planner_vs_compact-direct":bootstrap(records,"method-planner","compact-direct",reps),
      "compact-direct_vs_vanilla":bootstrap(records,"compact-direct","vanilla",reps)}
    p1=comps["method-planner_vs_vanilla"]; p2=comps["method-planner_vs_generic-planner"]
    pass1=bool(p1 and p1["mean_diff_points"]>=3.0 and p1["ci95"][0]>0)
    pass2=bool(p2 and p2["mean_diff_points"]>=1.5 and p2["ci95"][0]>0)
    dims=dim_means(records); va=dims["vanilla"].get("actionability"); ma=dims["method-planner"].get("actionability")
    action_delta=round(ma-va,3) if va is not None and ma is not None else None
    guardrail=bool(action_delta is not None and action_delta>=-0.10)
    executor_tokens={v:sum(answer_executor_tokens(r["answers"][v]) for r in records) for v in tg.VARIANTS}
    planner_tokens={v:sum(answer_planner_tokens(r["answers"][v]) for r in records) for v in tg.VARIANTS}
    total_tokens={v:executor_tokens[v]+planner_tokens[v] for v in tg.VARIANTS}
    lat={}; syschars={}; inputchars={}; stripped={}; failures={}; planner_stats={}
    for v in tg.VARIANTS:
        ans=[r["answers"][v] for r in records]
        l=[x["latency_s"] for x in ans if isinstance(x.get("latency_s"),(int,float))]; lat[v]=round(statistics.fmean(l),3) if l else None
        sc=[x["system_chars"] for x in ans if isinstance(x.get("system_chars"),int)]; syschars[v]=round(statistics.fmean(sc),1) if sc else None
        ic=[x["executor_input_chars"] for x in ans if isinstance(x.get("executor_input_chars"),int)]; inputchars[v]=round(statistics.fmean(ic),1) if ic else None
        stripped[v]=sum(int(x.get("reasoning_stripped_chars") or 0) for x in ans); failures[v]=sum(bool(x.get("error")) for x in ans)
        pls=[x.get("planner") for x in ans if x.get("planner")]
        if pls:
            counts=[len(p.get("selected_slugs") or []) for p in pls]
            planner_stats[v]={"calls":len(pls),"avg_selected_cards":round(statistics.fmean(counts),3) if counts else 0,"repairs":sum(bool(p.get("repair_attempted")) for p in pls),"errors":sum(bool(p.get("error")) for p in pls),"avg_planner_context_chars":round(statistics.fmean([p["planner_context_chars"] for p in pls]),1)}
        else: planner_stats[v]={"calls":0,"avg_selected_cards":0,"repairs":0,"errors":0,"avg_planner_context_chars":0}
    return {
      "suite":"task-gain-v3","architecture":"planner-executor-v3","task_files":freeze["task_files"],"rubric_git_blob":freeze["rubric_git_blob"],"planner_contract_git_blob":freeze["planner_contract_git_blob"],"runtime_cards_git_blob":freeze["runtime_cards_git_blob"],
      "generation_model":args.model,"judge_model":args.judge_model or args.model,"same_model_judge":(args.judge_model or args.model)==args.model,"cases_total":len(records),"judge_errors":sum(bool(r["judge"].get("error")) for r in records),"route_errors":sum(bool(r["route"].get("error")) for r in records),
      "variant_mean_scores_0_100":means,"category_mean_scores_0_100":category_means(records),"dimension_mean_scores_0_4":dims,"paired_comparisons":comps,
      "win_tie_loss":{"method-planner_vs_vanilla":wtl(records,"method-planner","vanilla"),"method-planner_vs_generic-planner":wtl(records,"method-planner","generic-planner"),"method-planner_vs_compact-direct":wtl(records,"method-planner","compact-direct")},
      "primary":{"method-planner_vs_vanilla_pass":pass1,"method-planner_vs_generic-planner_pass":pass2,"actionability_delta_0_4":action_delta,"actionability_guardrail_pass":guardrail,"overall_success":bool(pass1 and pass2 and guardrail),"success_rule":rubric["primary"]["overall_success_rule"]},
      "ceiling_diagnostic":{"vanilla_mean":means["vanilla"],"maximum_possible_mean_gain_to_100":round(100-means["vanilla"],3) if means["vanilla"] is not None else None},
      "per_hardness_feature_diffs":tag_diffs(records),"executor_tokens_by_variant":executor_tokens,"planner_tokens_by_variant":planner_tokens,"total_generation_and_planner_tokens_by_variant":total_tokens,"shared_router_tokens":sum(usage_tokens(r["route"]) for r in records),"judge_tokens":sum(usage_tokens(r["judge"]) for r in records),"avg_total_latency_s_by_variant":lat,"avg_executor_system_chars_by_variant":syschars,"avg_executor_input_chars_by_variant":inputchars,"planner_stats":planner_stats,"reasoning_stripped_chars_by_variant":stripped,"generation_failures_by_variant":failures}

def main():
    ap=argparse.ArgumentParser(description="Frozen Task Gain v3 benchmark for Planner -> Executor delivery.")
    ap.add_argument("--base-url",default=os.getenv("MAOXUAN_BENCH_BASE_URL")); ap.add_argument("--api-key",default=os.getenv("MAOXUAN_BENCH_API_KEY")); ap.add_argument("--model",default=os.getenv("MAOXUAN_BENCH_MODEL")); ap.add_argument("--judge-model",default=os.getenv("MAOXUAN_JUDGE_MODEL"))
    ap.add_argument("--workers",type=int,default=4); ap.add_argument("--judge-workers",type=int,default=2); ap.add_argument("--timeout",type=int,default=150); ap.add_argument("--no-response-format",action="store_true"); ap.add_argument("--output",default=str(RESULTS/"task-gain-v3.jsonl")); ap.add_argument("--dry-run",action="store_true")
    args=ap.parse_args(); tasks,rubric,freeze,contract=tg.load_suite(); schema=tg.rb.load_schema(); cards=tg.load_cards(); route_system=tg.hb.build_catalog_single_prompt(schema)
    if args.dry_run:
        by={}; tags={}
        for t in tasks:
            by[t["category"]]=by.get(t["category"],0)+1
            for tag in t["hardness_features"]: tags[tag]=tags.get(tag,0)+1
        sample_route={"route":"method_application","framework":None,"atomic_skills":["diaocha-yanjiu","shishiqiushi-sigao"],"composite":None,"components":[]}; selected=tg.selected_cards(sample_route,cards,contract)
        print(json.dumps({"ok":True,"suite":"task-gain-v3","cases":len(tasks),"variants":tg.VARIANTS,"by_category":by,"hardness_tags":len(tags),"router":"catalog-single / frozen","max_method_cards":contract["max_method_cards"],"sample_selected_cards":[c["slug"] for c in selected],"task_files":freeze["task_files"],"rubric_git_blob":freeze["rubric_git_blob"],"planner_contract_git_blob":freeze["planner_contract_git_blob"],"runtime_cards_git_blob":freeze["runtime_cards_git_blob"]},ensure_ascii=False,indent=2)); return
    if not args.base_url or not args.model: ap.error("set --base-url and --model")
    legacy.ensure_index(); rargs=SimpleNamespace(base_url=args.base_url,api_key=args.api_key,model=args.model,timeout=args.timeout,no_response_format=args.no_response_format)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,args.workers)) as ex: routes=list(ex.map(lambda c:legacy.route_one(c,rargs,schema,route_system),tasks))
    route_map={t["id"]:r for t,r in zip(tasks,routes)}; answers={t["id"]:{} for t in tasks}; jobs=[(t,v,route_map[t["id"]]["prediction"]) for t in tasks for v in tg.VARIANTS]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,args.workers)) as ex:
        futs={ex.submit(tg.answer_one,t,v,r,schema,cards,contract,args):(t["id"],v) for t,v,r in jobs}
        for f in concurrent.futures.as_completed(futs): tid,v=futs[f]; answers[tid][v]=f.result()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,args.judge_workers)) as ex: judges=list(ex.map(lambda t:tg.judge_one(t,answers[t["id"]],rubric,args),tasks))
    records=[]
    for t,j in zip(tasks,judges):
        scores={}
        for lab,v in j["label_map"].items(): scores[v]=legacy.weighted(t,j["scores"].get(lab,{})) if j["scores"] else None
        records.append({"id":t["id"],"category":t["category"],"prompt":t["prompt"],"reference_requirements":t["reference_requirements"],"hardness_features":t["hardness_features"],"weights":t["weights"],"route":route_map[t["id"]],"answers":answers[t["id"]],"judge":j,"variant_scores":scores})
    summary=summarize(records,rubric,freeze,contract,args); out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("w",encoding="utf-8") as f:
        for r in records: f.write(json.dumps(r,ensure_ascii=False)+"\n")
    sp=out.with_suffix(".summary.json"); sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2)); print(out); print(sp)

if __name__=="__main__": main()
