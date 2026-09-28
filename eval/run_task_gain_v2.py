#!/usr/bin/env python3
from __future__ import annotations
import argparse, concurrent.futures, json, os, random, statistics
from pathlib import Path
from types import SimpleNamespace
from task_gain_v2 import runtime as tg
from task_gain import runtime as legacy

ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/'eval/results'
METHOD_CATEGORIES={'research-decision','engineering-project','organization','learning-strategy'}

def tokens(items):
    return sum(int((x.get('usage') or {}).get('total_tokens') or 0) for x in items)

def bootstrap(records,a,b,reps,scope=None,seed=20260928):
    diffs=[]
    for r in records:
        if scope and r['category'] not in scope: continue
        x=r['variant_scores'].get(a); y=r['variant_scores'].get(b)
        if x is not None and y is not None: diffs.append(x-y)
    if not diffs: return None
    rng=random.Random(seed+sum(map(ord,a+b))); boots=[]; n=len(diffs)
    for _ in range(reps): boots.append(statistics.fmean(diffs[rng.randrange(n)] for __ in range(n)))
    boots.sort(); lo=boots[int(.025*(reps-1))]; hi=boots[int(.975*(reps-1))]
    return {'mean_diff_points':round(statistics.fmean(diffs),3),'ci95':[round(lo,3),round(hi,3)],'n':n}

def summarize(records,rubric,freeze,args):
    means={}; method_means={}; cats={}; gen_tokens={}; lats={}; chars={}; failures={}; cits={}
    categories=sorted({r['category'] for r in records})
    for v in tg.VARIANTS:
        xs=[r['variant_scores'][v] for r in records if r['variant_scores'].get(v) is not None]
        means[v]=round(statistics.fmean(xs),3) if xs else None
        mx=[r['variant_scores'][v] for r in records if r['category'] in METHOD_CATEGORIES and r['variant_scores'].get(v) is not None]
        method_means[v]=round(statistics.fmean(mx),3) if mx else None
        cats[v]={}
        for c in categories:
            ys=[r['variant_scores'][v] for r in records if r['category']==c and r['variant_scores'].get(v) is not None]
            cats[v][c]=round(statistics.fmean(ys),3) if ys else None
        ans=[r['answers'][v] for r in records]
        gen_tokens[v]=tokens(ans)
        vl=[x['latency_s'] for x in ans if isinstance(x.get('latency_s'),(int,float))]
        lats[v]=round(statistics.fmean(vl),3) if vl else None
        sc=[x['system_chars'] for x in ans if isinstance(x.get('system_chars'),int)]
        chars[v]=round(statistics.fmean(sc),1) if sc else None
        failures[v]=sum(bool(x.get('error')) for x in ans)
        src=[r['citation_stats'][v] for r in records if r['category']=='source-evidence']
        tc=sum(x['count'] for x in src); tv=sum(x['valid_count'] for x in src)
        cits[v]={'source_tasks_with_valid_citation':f"{sum(x['has_valid_citation'] for x in src)}/{len(src)}",'citation_precision':round(tv/tc,4) if tc else None,'citations_total':tc,'valid_citations_total':tv}
    reps=int(rubric['reporting']['paired_bootstrap_reps'])
    comps={
      'compact-atomic_vs_vanilla_method':bootstrap(records,'compact-atomic','vanilla',reps,METHOD_CATEGORIES),
      'legacy-raw_vs_vanilla_method':bootstrap(records,'legacy-raw','vanilla',reps,METHOD_CATEGORIES),
      'compact-atomic_vs_legacy-raw_method':bootstrap(records,'compact-atomic','legacy-raw',reps,METHOD_CATEGORIES),
      'full-v2_vs_vanilla_all':bootstrap(records,'full-v2','vanilla',reps,None),
      'full-v2_vs_vanilla_method':bootstrap(records,'full-v2','vanilla',reps,METHOD_CATEGORIES),
      'retrieval-only_vs_vanilla_source':bootstrap(records,'retrieval-only','vanilla',reps,{'source-evidence'}),
      'full-v2_vs_retrieval-only_source':bootstrap(records,'full-v2','retrieval-only',reps,{'source-evidence'})}
    primary=comps['compact-atomic_vs_vanilla_method']; threshold=float(rubric['meaningful_gain_threshold_points'])
    primary_met=bool(primary and primary['mean_diff_points']>=threshold and primary['ci95'][0]>0)
    return {'suite':'task-gain-v2','tasks_git_blob':freeze['tasks_git_blob'],'rubric_git_blob':freeze['rubric_git_blob'],'runtime_cards_git_blob':freeze['runtime_cards_git_blob'],'tasks_sha256':tg.sha256(ROOT/'eval/task_gain_v2/tasks-v2.jsonl'),'rubric_sha256':tg.sha256(ROOT/'eval/task_gain_v2/rubric-v2.json'),'runtime_cards_sha256':tg.sha256(ROOT/'skills/runtime/RUNTIME_CARDS.json'),'generation_model':args.model,'judge_model':args.judge_model or args.model,'same_model_judge':(args.judge_model or args.model)==args.model,'cases_total':len(records),'method_cases_total':sum(r['category'] in METHOD_CATEGORIES for r in records),'judge_errors':sum(bool(r['judge'].get('error')) for r in records),'route_errors':sum(bool(r['route'].get('error')) for r in records),'variant_mean_scores_0_100':means,'method_mean_scores_0_100':method_means,'category_mean_scores_0_100':cats,'paired_comparisons':comps,'primary_meaningful_gain_threshold_points':threshold,'primary_success_rule':rubric['primary']['success_rule'],'primary_threshold_met':primary_met,'generation_tokens_by_variant':gen_tokens,'shared_router_tokens':tokens([r['route'] for r in records]),'judge_tokens':tokens([r['judge'] for r in records]),'avg_generation_latency_s_by_variant':lats,'avg_system_chars_by_variant':chars,'generation_failures_by_variant':failures,'source_citation_validity':cits}

def main():
    ap=argparse.ArgumentParser(description='Frozen Task Gain v2 benchmark for compact Runtime Skills.')
    ap.add_argument('--base-url',default=os.getenv('MAOXUAN_BENCH_BASE_URL')); ap.add_argument('--api-key',default=os.getenv('MAOXUAN_BENCH_API_KEY'))
    ap.add_argument('--model',default=os.getenv('MAOXUAN_BENCH_MODEL')); ap.add_argument('--judge-model',default=os.getenv('MAOXUAN_JUDGE_MODEL'))
    ap.add_argument('--workers',type=int,default=4); ap.add_argument('--judge-workers',type=int,default=2); ap.add_argument('--timeout',type=int,default=120)
    ap.add_argument('--no-response-format',action='store_true'); ap.add_argument('--output',default=str(RESULTS/'task-gain-v2.jsonl')); ap.add_argument('--dry-run',action='store_true')
    args=ap.parse_args(); tasks,rubric,freeze=tg.load_suite(); schema=tg.rb.load_schema(); cards,comps=tg.load_cards(); route_system=tg.hb.build_catalog_single_prompt(schema)
    if args.dry_run:
        by={}
        for t in tasks: by[t['category']]=by.get(t['category'],0)+1
        sample_route={'route':'method_application','framework':None,'atomic_skills':['diaocha-yanjiu','shishiqiushi-sigao'],'composite':None,'components':[]}
        sample=tg.variant_system('compact-atomic',tasks[8],sample_route,schema,[],cards,comps)
        print(json.dumps({'ok':True,'suite':'task-gain-v2','cases':len(tasks),'variants':tg.VARIANTS,'by_category':by,'tasks_git_blob':freeze['tasks_git_blob'],'rubric_git_blob':freeze['rubric_git_blob'],'runtime_cards_git_blob':freeze['runtime_cards_git_blob'],'router':'catalog-single / frozen','sample_compact_system_chars':len(sample)},ensure_ascii=False,indent=2)); return
    if not args.base_url or not args.model: ap.error('set --base-url and --model')
    legacy.ensure_index(); rargs=SimpleNamespace(base_url=args.base_url,api_key=args.api_key,model=args.model,timeout=args.timeout,no_response_format=args.no_response_format)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,args.workers)) as ex: routes=list(ex.map(lambda c:legacy.route_one(c,rargs,schema,route_system),tasks))
    route_map={t['id']:r for t,r in zip(tasks,routes)}; retrieval={t['id']:legacy.retrieve(t) for t in tasks}; answers={t['id']:{} for t in tasks}
    jobs=[(t,v,route_map[t['id']]['prediction'],retrieval[t['id']]) for t in tasks for v in tg.VARIANTS]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,args.workers)) as ex:
        futs={ex.submit(tg.answer_one,t,v,r,schema,rows,cards,comps,args):(t['id'],v) for t,v,r,rows in jobs}
        for f in concurrent.futures.as_completed(futs): tid,v=futs[f]; answers[tid][v]=f.result()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,args.judge_workers)) as ex: judges=list(ex.map(lambda t:tg.judge_one(t,answers[t['id']],rubric,args),tasks))
    records=[]
    for t,j in zip(tasks,judges):
        scores={}
        for lab,v in j['label_map'].items(): scores[v]=legacy.weighted(t,j['scores'].get(lab,{})) if j['scores'] else None
        valid={x['source_id'] for x in retrieval[t['id']]}
        records.append({'id':t['id'],'category':t['category'],'prompt':t['prompt'],'reference_requirements':t['reference_requirements'],'weights':t['weights'],'route':route_map[t['id']],'retrieval':retrieval[t['id']],'answers':answers[t['id']],'judge':j,'variant_scores':scores,'citation_stats':{v:legacy.citation_stats(answers[t['id']][v]['text'],valid) for v in tg.VARIANTS}})
    summary=summarize(records,rubric,freeze,args); out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('w',encoding='utf-8') as f:
        for r in records: f.write(json.dumps(r,ensure_ascii=False)+'\n')
    sp=out.with_suffix('.summary.json'); sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2)); print(out); print(sp)

if __name__=='__main__': main()
