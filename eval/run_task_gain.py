#!/usr/bin/env python3
from __future__ import annotations
import argparse, concurrent.futures, json, os, statistics
from pathlib import Path
from types import SimpleNamespace
from task_gain import runtime as tg

ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/"eval/results"

def summarize(records,rubric,freeze,args):
    means={}; cats={}; gen_tokens={}; lats={}; cits={}
    categories=sorted({r["category"] for r in records})
    for v in tg.VARIANTS:
        xs=[r["variant_scores"][v] for r in records if r["variant_scores"].get(v) is not None]
        means[v]=round(statistics.fmean(xs),3) if xs else None
        cats[v]={}
        for c in categories:
            ys=[r["variant_scores"][v] for r in records if r["category"]==c and r["variant_scores"].get(v) is not None]
            cats[v][c]=round(statistics.fmean(ys),3) if ys else None
        gen_tokens[v]=tg.tokens([r["answers"][v] for r in records])
        vl=[r["answers"][v]["latency_s"] for r in records if isinstance(r["answers"][v].get("latency_s"),(int,float))]
        lats[v]=round(statistics.fmean(vl),3) if vl else None
        src=[r["citation_stats"][v] for r in records if r["category"]=="source-evidence"]
        tc=sum(x["count"] for x in src); tv=sum(x["valid_count"] for x in src)
        cits[v]={"source_tasks_with_valid_citation":f"{sum(x['has_valid_citation'] for x in src)}/{len(src)}",
                 "citation_precision":round(tv/tc,4) if tc else None,"citations_total":tc,"valid_citations_total":tv}
    reps=int(rubric["reporting"]["paired_bootstrap_reps"])
    comps={
      "full-system_vs_vanilla":tg.bootstrap(records,"full-system","vanilla",reps),
      "retrieval-only_vs_vanilla":tg.bootstrap(records,"retrieval-only","vanilla",reps),
      "atomic_vs_vanilla":tg.bootstrap(records,"atomic","vanilla",reps),
      "framework-atomic_vs_atomic":tg.bootstrap(records,"framework-atomic","atomic",reps),
      "full-system_vs_framework-atomic":tg.bootstrap(records,"full-system","framework-atomic",reps)}
    primary=comps["full-system_vs_vanilla"]; threshold=float(rubric["meaningful_gain_threshold_points"])
    return {"suite":"task-gain-v1","tasks_sha256":freeze["tasks_sha256"],"rubric_sha256":freeze["rubric_sha256"],
            "generation_model":args.model,"judge_model":args.judge_model or args.model,
            "same_model_judge":(args.judge_model or args.model)==args.model,"cases_total":len(records),
            "judge_errors":sum(bool(r["judge"].get("error")) for r in records),
            "route_errors":sum(bool(r["route"].get("error")) for r in records),
            "variant_mean_scores_0_100":means,"category_mean_scores_0_100":cats,"paired_comparisons":comps,
            "primary_meaningful_gain_threshold_points":threshold,
            "primary_threshold_met":bool(primary and primary["mean_diff_points"]>=threshold),
            "generation_tokens_by_variant":gen_tokens,
            "shared_router_tokens":tg.tokens([r["route"] for r in records]),
            "judge_tokens":tg.tokens([r["judge"] for r in records]),
            "avg_generation_latency_s_by_variant":lats,"source_citation_validity":cits}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--base-url",default=os.getenv("MAOXUAN_BENCH_BASE_URL"))
    ap.add_argument("--api-key",default=os.getenv("MAOXUAN_BENCH_API_KEY"))
    ap.add_argument("--model",default=os.getenv("MAOXUAN_BENCH_MODEL"))
    ap.add_argument("--judge-model",default=os.getenv("MAOXUAN_JUDGE_MODEL"))
    ap.add_argument("--workers",type=int,default=4); ap.add_argument("--judge-workers",type=int,default=2)
    ap.add_argument("--timeout",type=int,default=120); ap.add_argument("--no-response-format",action="store_true")
    ap.add_argument("--output",default=str(RESULTS/"task-gain-v1.jsonl")); ap.add_argument("--dry-run",action="store_true")
    args=ap.parse_args()
    tasks,rubric,freeze=tg.load_suite(); schema=tg.rb.load_schema(); route_system=tg.hb.build_catalog_single_prompt(schema)
    if args.dry_run:
        by={}
        for t in tasks: by[t["category"]]=by.get(t["category"],0)+1
        print(json.dumps({"ok":True,"suite":"task-gain-v1","cases":len(tasks),"variants":tg.VARIANTS,
                          "by_category":by,"tasks_sha256":freeze["tasks_sha256"],"rubric_sha256":freeze["rubric_sha256"],
                          "router":"catalog-single / frozen","route_system_chars":len(route_system)},ensure_ascii=False,indent=2)); return
    if not args.base_url or not args.model: ap.error("set --base-url and --model")
    tg.ensure_index()
    rargs=SimpleNamespace(base_url=args.base_url,api_key=args.api_key,model=args.model,timeout=args.timeout,
                          no_response_format=args.no_response_format)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,args.workers)) as ex:
        routes=list(ex.map(lambda c:tg.route_one(c,rargs,schema,route_system),tasks))
    route_map={t["id"]:r for t,r in zip(tasks,routes)}
    retrieval={t["id"]:tg.retrieve(t) for t in tasks}
    answers={t["id"]:{} for t in tasks}
    jobs=[(t,v,route_map[t["id"]]["prediction"],retrieval[t["id"]]) for t in tasks for v in tg.VARIANTS]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,args.workers)) as ex:
        futs={ex.submit(tg.answer_one,t,v,r,schema,rows,args):(t["id"],v) for t,v,r,rows in jobs}
        for f in concurrent.futures.as_completed(futs):
            tid,v=futs[f]; answers[tid][v]=f.result()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,args.judge_workers)) as ex:
        judges=list(ex.map(lambda t:tg.judge_one(t,answers[t["id"]],rubric,args),tasks))
    records=[]
    for t,j in zip(tasks,judges):
        scores={}
        for lab,v in j["label_map"].items(): scores[v]=tg.weighted(t,j["scores"].get(lab,{})) if j["scores"] else None
        valid={x["source_id"] for x in retrieval[t["id"]]}
        records.append({"id":t["id"],"category":t["category"],"prompt":t["prompt"],
                        "reference_requirements":t["reference_requirements"],"weights":t["weights"],
                        "route":route_map[t["id"]],"retrieval":retrieval[t["id"]],"answers":answers[t["id"]],
                        "judge":j,"variant_scores":scores,
                        "citation_stats":{v:tg.citation_stats(answers[t["id"]][v]["text"],valid) for v in tg.VARIANTS}})
    summary=summarize(records,rubric,freeze,args); out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("w",encoding="utf-8") as f:
        for r in records: f.write(json.dumps(r,ensure_ascii=False)+"\n")
    sp=out.with_suffix(".summary.json"); sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2)); print(out); print(sp)
if __name__=="__main__": main()
