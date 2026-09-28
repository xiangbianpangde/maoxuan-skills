#!/usr/bin/env python3
from __future__ import annotations
import argparse, concurrent.futures, json, os, random, statistics
from pathlib import Path
from types import SimpleNamespace

from task_gain_v4 import runtime as tg
from task_gain import runtime as legacy

ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/"eval/results"

def usage_tokens(obj):
    return int(((obj or {}).get("usage") or {}).get("total_tokens") or 0)

def bootstrap(records,a,b,reps,seed):
    ds=[r["variant_scores"][a]-r["variant_scores"][b] for r in records if r["variant_scores"].get(a) is not None and r["variant_scores"].get(b) is not None]
    if not ds:return None
    rng=random.Random(seed+sum(map(ord,a+b))); n=len(ds); boots=[]
    for _ in range(reps):boots.append(statistics.fmean(ds[rng.randrange(n)] for __ in range(n)))
    boots.sort()
    return {"mean_diff_points":round(statistics.fmean(ds),3),"ci95":[round(boots[int(.025*(reps-1))],3),round(boots[int(.975*(reps-1))],3)],"n":n}

def wtl(records,a,b):
    w=t=l=0
    for r in records:
        x=r["variant_scores"].get(a); y=r["variant_scores"].get(b)
        if x is None or y is None:continue
        d=round(x-y,9)
        if d>0:w+=1
        elif d<0:l+=1
        else:t+=1
    return {"wins":w,"ties":t,"losses":l}

def dim_means(records):
    vals={v:{} for v in tg.VARIANTS}
    for r in records:
        for lab,v in r["judge"]["label_map"].items():
            for d,x in (r["judge"]["scores"].get(lab) or {}).items():vals[v].setdefault(d,[]).append(float(x))
    return {v:{d:round(statistics.fmean(xs),3) for d,xs in sorted(vals[v].items())} for v in tg.VARIANTS}

def category_means(records):
    cats=sorted({r["category"] for r in records}); out={}
    for v in tg.VARIANTS:
        out[v]={}
        for c in cats:
            xs=[r["variant_scores"][v] for r in records if r["category"]==c and r["variant_scores"].get(v) is not None]
            out[v][c]=round(statistics.fmean(xs),3) if xs else None
    return out

def tag_diffs(records):
    tags=sorted({x for r in records for x in r["hardness_features"]}); out={}
    for tag in tags:
        rs=[r for r in records if tag in r["hardness_features"]]
        def md(a,b):
            ds=[r["variant_scores"][a]-r["variant_scores"][b] for r in rs]
            return round(statistics.fmean(ds),3) if ds else None
        out[tag]={"n":len(rs),"generic_vs_vanilla":md("generic-planner","vanilla"),"method_vs_generic":md("method-planner","generic-planner")}
    return out

def summarize(records,rubric,freeze,args):
    means={}
    for v in tg.VARIANTS:
        xs=[r["variant_scores"][v] for r in records if r["variant_scores"].get(v) is not None]
        means[v]=round(statistics.fmean(xs),3) if xs else None
    reps=int(rubric["reporting"]["paired_bootstrap_reps"]); seed=int(rubric["reporting"]["bootstrap_seed"])
    comps={"generic-planner_vs_vanilla":bootstrap(records,"generic-planner","vanilla",reps,seed),"method-planner_vs_generic-planner":bootstrap(records,"method-planner","generic-planner",reps,seed),"method-planner_vs_vanilla":bootstrap(records,"method-planner","vanilla",reps,seed)}
    dims=dim_means(records); planner_meta={}; failures={}; fallbacks={}; tokens={}; planner_tokens={}; latency={}; stripped={}; normalizations={}
    for v in tg.VARIANTS:
        ans=[r["answers"][v] for r in records]
        failures[v]=sum(bool(x.get("error")) for x in ans); fallbacks[v]=sum(bool(x.get("fallback_used")) for x in ans)
        tokens[v]=sum(usage_tokens(x) for x in ans); planner_tokens[v]=sum(usage_tokens(x.get("planner")) for x in ans if x.get("planner"))
        ls=[x["latency_s"] for x in ans if isinstance(x.get("latency_s"),(int,float))]; latency[v]=round(statistics.fmean(ls),3) if ls else None
        stripped[v]=sum(int(x.get("reasoning_stripped_chars") or 0) for x in ans); ps=[x.get("planner") for x in ans if x.get("planner")]
        planner_meta[v]={"calls":len(ps),"errors":sum(bool(p.get("error")) for p in ps),"repairs":sum(bool(p.get("repair_attempted")) for p in ps),"avg_selected_cards":round(statistics.fmean([len(p.get("selected_slugs") or []) for p in ps]),3) if ps else 0}
        counts={}
        for p in ps:
            for n in p.get("normalizations") or []:counts[n]=counts.get(n,0)+1
        normalizations[v]=counts
    p1=comps["generic-planner_vs_vanilla"]; p2=comps["method-planner_vs_generic-planner"]
    planning_pass=bool(p1 and p1["mean_diff_points"]>=2.0 and p1["ci95"][0]>0); method_increment_pass=bool(p2 and p2["mean_diff_points"]>=1.5 and p2["ci95"][0]>0)
    ad=round(dims["method-planner"].get("actionability",0)-dims["generic-planner"].get("actionability",0),3)
    reliability_pass=(all(failures[v]==0 for v in tg.VARIANTS) and fallbacks["generic-planner"]<=1 and fallbacks["method-planner"]<=1)
    actionability_pass=ad>=-0.10; planning_claim=bool(planning_pass and reliability_pass); method_claim=bool(method_increment_pass and reliability_pass and actionability_pass)
    if method_claim:decision="method-planner-candidate"
    elif planning_claim:decision="generic-planner-candidate; no Method-Card incremental claim"
    else:decision="vanilla-default; no default planner claim"
    return {"suite":"task-gain-v4","architecture":"reliable-planner-attribution-v4","tasks_git_blob":freeze["tasks_git_blob"],"rubric_git_blob":freeze["rubric_git_blob"],"planner_reliability_policy_git_blob":freeze["planner_reliability_policy_git_blob"],"planner_contract_git_blob":freeze["planner_contract_git_blob"],"runtime_cards_git_blob":freeze["runtime_cards_git_blob"],"generation_model":args.model,"judge_model":args.judge_model or args.model,"same_model_judge":(args.judge_model or args.model)==args.model,"cases_total":len(records),"judge_errors":sum(bool(r["judge"].get("error")) for r in records),"route_errors":sum(bool(r["route"].get("error")) for r in records),"variant_mean_scores_0_100":means,"category_mean_scores_0_100":category_means(records),"dimension_mean_scores_0_4":dims,"paired_comparisons":comps,"win_tie_loss":{"generic-planner_vs_vanilla":wtl(records,"generic-planner","vanilla"),"method-planner_vs_generic-planner":wtl(records,"method-planner","generic-planner")},"primary":{"planning_hypothesis_pass":planning_pass,"method_increment_hypothesis_pass":method_increment_pass,"reliability_guardrail_pass":reliability_pass,"method_actionability_delta_vs_generic_0_4":ad,"actionability_guardrail_pass":actionability_pass,"planning_claim_pass":planning_claim,"method_card_incremental_claim_pass":method_claim,"runtime_decision":decision},"ceiling_diagnostic":{"vanilla_mean":means["vanilla"],"maximum_possible_mean_gain_to_100":round(100-means["vanilla"],3) if means["vanilla"] is not None else None},"per_hardness_feature_diffs":tag_diffs(records),"generation_failures_by_variant":failures,"planner_fallbacks_by_variant":fallbacks,"planner_stats":planner_meta,"normalization_counts":normalizations,"executor_tokens_by_variant":tokens,"planner_tokens_by_variant":planner_tokens,"total_tokens_by_variant":{v:tokens[v]+planner_tokens[v] for v in tg.VARIANTS},"avg_total_latency_s_by_variant":latency,"reasoning_stripped_chars_by_variant":stripped}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--base-url",default=os.getenv("MAOXUAN_BENCH_BASE_URL")); ap.add_argument("--api-key",default=os.getenv("MAOXUAN_BENCH_API_KEY")); ap.add_argument("--model",default=os.getenv("MAOXUAN_BENCH_MODEL")); ap.add_argument("--judge-model",default=os.getenv("MAOXUAN_JUDGE_MODEL")); ap.add_argument("--workers",type=int,default=4); ap.add_argument("--judge-workers",type=int,default=2); ap.add_argument("--timeout",type=int,default=150); ap.add_argument("--no-response-format",action="store_true"); ap.add_argument("--output",default=str(RESULTS/"task-gain-v4.jsonl")); ap.add_argument("--dry-run",action="store_true"); args=ap.parse_args()
    tasks,rubric,freeze,contract,policy=tg.load_suite(); schema=tg.rb.load_schema(); cards=tg.load_cards(); route_system=tg.hb.build_catalog_single_prompt(schema)
    if args.dry_run:
        by={}
        for t in tasks:by[t["category"]]=by.get(t["category"],0)+1
        print(json.dumps({"ok":True,"suite":"task-gain-v4","cases":len(tasks),"variants":tg.VARIANTS,"by_category":by,"tasks_git_blob":freeze["tasks_git_blob"],"rubric_git_blob":freeze["rubric_git_blob"],"runtime_cards_git_blob":freeze["runtime_cards_git_blob"],"router":"catalog-single / frozen","fail_open":policy["fail_open"]["enabled"]},ensure_ascii=False,indent=2)); return
    if not args.base_url or not args.model:ap.error("set --base-url and --model")
    legacy.ensure_index(); rargs=SimpleNamespace(base_url=args.base_url,api_key=args.api_key,model=args.model,timeout=args.timeout,no_response_format=args.no_response_format)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,args.workers)) as ex:routes=list(ex.map(lambda c:legacy.route_one(c,rargs,schema,route_system),tasks))
    route_map={t["id"]:r for t,r in zip(tasks,routes)}; answers={t["id"]:{} for t in tasks}; jobs=[(t,v,route_map[t["id"]]["prediction"]) for t in tasks for v in tg.VARIANTS]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,args.workers)) as ex:
        futs={ex.submit(tg.answer_one,t,v,r,schema,cards,contract,policy,args):(t["id"],v) for t,v,r in jobs}
        for f in concurrent.futures.as_completed(futs):tid,v=futs[f]; answers[tid][v]=f.result()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,args.judge_workers)) as ex:judges=list(ex.map(lambda t:tg.judge_one(t,answers[t["id"]],rubric,args),tasks))
    records=[]
    for t,j in zip(tasks,judges):
        scores={}
        for lab,v in j["label_map"].items():scores[v]=legacy.weighted(t,j["scores"].get(lab,{})) if j["scores"] else None
        records.append({"id":t["id"],"category":t["category"],"prompt":t["prompt"],"reference_requirements":t["reference_requirements"],"hardness_features":t["hardness_features"],"weights":t["weights"],"route":route_map[t["id"]],"answers":answers[t["id"]],"judge":j,"variant_scores":scores})
    summary=summarize(records,rubric,freeze,args); out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("w",encoding="utf-8") as f:
        for r in records:f.write(json.dumps(r,ensure_ascii=False)+"\n")
    sp=out.with_suffix(".summary.json"); sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps(summary,ensure_ascii=False,indent=2)); print(out); print(sp)

if __name__=="__main__":main()
