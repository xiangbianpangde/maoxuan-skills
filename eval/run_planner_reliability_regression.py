#!/usr/bin/env python3
from __future__ import annotations
import argparse, concurrent.futures, json, os, sys
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT/"eval") not in sys.path:sys.path.insert(0,str(ROOT/"eval"))

from task_gain_v3 import runtime as v3
from task_gain_v4 import runtime as v4
from task_gain import runtime as legacy

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--base-url",default=os.getenv("MAOXUAN_BENCH_BASE_URL")); ap.add_argument("--api-key",default=os.getenv("MAOXUAN_BENCH_API_KEY")); ap.add_argument("--model",default=os.getenv("MAOXUAN_BENCH_MODEL")); ap.add_argument("--workers",type=int,default=4); ap.add_argument("--timeout",type=int,default=150); ap.add_argument("--no-response-format",action="store_true"); ap.add_argument("--require-zero",action="store_true"); args=ap.parse_args()
    if not args.base_url or not args.model:ap.error("set --base-url and --model")
    tasks,_,_,contract=v3.load_suite(); policy=json.loads((ROOT/"skills/runtime/PLANNER_RELIABILITY_V4.json").read_text(encoding="utf-8")); schema=v3.rb.load_schema(); cards=v4.load_cards(); route_system=v3.hb.build_catalog_single_prompt(schema); legacy.ensure_index()
    rargs=SimpleNamespace(base_url=args.base_url,api_key=args.api_key,model=args.model,timeout=args.timeout,no_response_format=args.no_response_format)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,args.workers)) as ex:routes=list(ex.map(lambda c:legacy.route_one(c,rargs,schema,route_system),tasks))
    route_map={t["id"]:r["prediction"] for t,r in zip(tasks,routes)}; jobs=[(t,mode) for t in tasks for mode in ("generic","method")]
    def one(job):
        t,mode=job; p=v4.call_planner(t,route_map[t["id"]],cards,contract,policy,args,with_methods=(mode=="method"))
        return {"id":t["id"],"mode":mode,"error":p["error"],"repair_attempted":p["repair_attempted"],"normalizations":p["normalizations"],"selected_slugs":p["selected_slugs"]}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,args.workers)) as ex:rows=list(ex.map(one,jobs))
    errors=[x for x in rows if x["error"]]
    summary={"suite":"v3-planner-reliability-regression","tasks":len(tasks),"planner_calls":len(rows),"errors_total":len(errors),"generic_errors":sum(x["mode"]=="generic" and bool(x["error"]) for x in rows),"method_errors":sum(x["mode"]=="method" and bool(x["error"]) for x in rows),"repairs":sum(bool(x["repair_attempted"]) for x in rows),"normalizations":sum(len(x["normalizations"]) for x in rows),"errors":errors}
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    if args.require_zero and errors:raise SystemExit(2)

if __name__=="__main__":main()
