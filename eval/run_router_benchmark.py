#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
ATOMIC_DATASET = ROOT / 'eval/atomic-routing-benchmark.generated.jsonl'
ROUTER_TESTS = ROOT / 'router/routing-tests.json'
CATALOG = ROOT / 'skills/atomic/CATALOG.json'
FRAMEWORKS = ROOT / 'skills/frameworks/FRAMEWORKS.json'
RESULTS_DIR = ROOT / 'eval/results'


def ensure_atomic_dataset() -> None:
    if ATOMIC_DATASET.exists():
        return
    subprocess.run([sys.executable, str(ROOT / 'eval/build_atomic_benchmark.py')], cwd=ROOT, check=True)


def load_cases() -> list[dict]:
    ensure_atomic_dataset()
    cases=[]
    for line in ATOMIC_DATASET.read_text(encoding='utf-8').splitlines():
        if line.strip():
            item=json.loads(line)
            item['benchmark_level']='atomic'
            cases.append(item)
    rt=json.loads(ROUTER_TESTS.read_text(encoding='utf-8'))
    for c in rt['cases']:
        cases.append({
            'id':f"system:{c['id']}",
            'benchmark_level':'system_router',
            'prompt':c['prompt'],
            'expected_route':c['expected_route'],
            'expected_framework':c.get('expected_framework'),
            'expected_atomic':c.get('expected_atomic',[]),
            'expected_composite':c.get('expected_composite'),
            'expected_components':c.get('expected_components',[]),
            'type':'system_router'
        })
    return cases


def _stable_rank(case: dict) -> str:
    return hashlib.sha256(case['id'].encode('utf-8')).hexdigest()


def stratified_sample(cases: list[dict], limit: int | None) -> list[dict]:
    """Deterministic proportional sample across case types.

    A small smoke run should not be the first N rows of a skill-grouped dataset,
    otherwise it measures only the first few atomic skills.
    """
    if not limit or limit >= len(cases):
        return cases
    if limit <= 0:
        return []

    buckets: dict[str,list[dict]]={}
    for case in cases:
        buckets.setdefault(case.get('type') or 'unknown',[]).append(case)
    nonempty={k:v for k,v in buckets.items() if v}
    total=sum(len(v) for v in nonempty.values())

    raw={k: limit*len(v)/total for k,v in nonempty.items()}
    quota={k:min(len(nonempty[k]), math.floor(raw[k])) for k in nonempty}
    remaining=limit-sum(quota.values())
    remainder_order=sorted(
        nonempty,
        key=lambda k:(raw[k]-math.floor(raw[k]), len(nonempty[k]), k),
        reverse=True,
    )
    while remaining>0:
        progressed=False
        for k in remainder_order:
            if quota[k] < len(nonempty[k]):
                quota[k]+=1
                remaining-=1
                progressed=True
                if remaining==0:
                    break
        if not progressed:
            break

    selected=[]
    for k,items in nonempty.items():
        selected.extend(sorted(items,key=_stable_rank)[:quota[k]])
    return sorted(selected,key=lambda c:c['id'])


def build_system_prompt() -> str:
    catalog=json.loads(CATALOG.read_text(encoding='utf-8'))
    fw=json.loads(FRAMEWORKS.read_text(encoding='utf-8'))
    skill_lines=[f"- {x['slug']} ({x['name']}): {x['summary']}" for x in catalog['skills']]
    framework_lines=[f"- {x['id']}: {', '.join(x['atomic_skills'])}" for x in fw['frameworks']]
    composites=[p.parent.name for p in sorted((ROOT/'skills/composite').glob('*/SKILL.md'))]
    return f"""You are the routing evaluator for a layered Selected Works methodology skill system.
Classify the user's request; do not answer the substantive question.

First apply a skill-necessity gate. The default is direct when this special methodology system does not materially improve the task.
Do NOT select a methodology skill merely because the user has a problem, decision, disagreement, bug, or learning request.

Routes:
- direct: no Selected Works retrieval or methodology skill is needed; answer normally outside this skill system.
- source_lookup: original text, citation, article meaning, textual/historical explanation. Use component retrieval.
- method_application: a focused non-political problem where one framework and 1-4 atomic skills materially improve the analysis.
- composite_task: a genuinely multi-stage non-political analysis requiring a composite workflow.
- mixed: both original-source evidence and method application are materially required.

Use direct for ordinary tutorial/resource recommendations, straightforward verification/calculation, a single well-scoped implementation bug, aesthetic/formatting choices, and routine one-off preferences unless the user explicitly asks for deeper methodology analysis.
Choose the smallest sufficient set of atomic skills. Zero atomic skills is correct for direct and source_lookup. Avoid adding adjacent skills "just in case".

Atomic skills and routing summaries:
{chr(10).join(skill_lines)}

Important discrimination rules:
- shijian-renshilun: use when an action -> feedback -> revised-understanding loop is central; not for a generic tutorial/resource request.
- shishiqiushi-sigao: use when messy/raw evidence must be filtered, verified, connected, or synthesized; not for checking already-computed arithmetic or choosing visual style.
- maodun-fenxi: use when the task requires prioritizing among multiple competing problems/forces or finding a principal bottleneck; not for a single known bug or a trivial preference dispute.
- maodun-techuxing: use when a benchmark/template/method is being mechanically copied across different conditions, or when a once-effective method stops working because conditions changed. It is about context-specific method fit, not generic root-cause analysis.
- diaocha-yanjiu: use when a consequential judgment is blocked by missing first-hand facts or untested assumptions; not for every request that could benefit from more information.

Framework -> atomic map:
{chr(10).join(framework_lines)}

Composite workflows: {', '.join(composites)}

Political neutrality boundary: for current politics, elections, parties, officials, legislation, ballot measures, or political persuasion, do not route into strategic persuasion/action skills. Source lookup and neutral factual comparison are allowed.
Historical military-origin skills may only be routed for explicitly non-violent domains such as product, engineering, research, project management, organizational learning, or lawful business competition.

Return JSON only with this schema:
{{"route":"direct|source_lookup|method_application|composite_task|mixed","framework":null,"atomic_skills":[],"composite":null,"components":[]}}
Do not include prose outside JSON."""


def parse_json_object(text: str) -> dict:
    text=text.strip()
    if text.startswith('```'):
        text=text.strip('`').strip()
        if text.lower().startswith('json'):
            text=text[4:].strip()
    try:
        value=json.loads(text)
        if isinstance(value,dict): return value
    except json.JSONDecodeError:
        pass
    dec=json.JSONDecoder()
    for i,ch in enumerate(text):
        if ch!='{': continue
        try:
            value,_=dec.raw_decode(text[i:])
            if isinstance(value,dict): return value
        except json.JSONDecodeError:
            continue
    raise ValueError('model output does not contain a JSON object')


def post_chat(base_url: str, api_key: str | None, model: str, system: str, prompt: str, timeout: int, use_response_format: bool) -> tuple[str,dict]:
    url=base_url.rstrip('/')+'/chat/completions'
    body={
        'model':model,
        'messages':[{'role':'system','content':system},{'role':'user','content':prompt}],
        'temperature':0
    }
    if use_response_format:
        body['response_format']={'type':'json_object'}
    data=json.dumps(body,ensure_ascii=False).encode('utf-8')
    headers={'Content-Type':'application/json'}
    if api_key:
        headers['Authorization']='Bearer '+api_key
    req=urllib.request.Request(url,data=data,headers=headers,method='POST')
    try:
        with urllib.request.urlopen(req,timeout=timeout) as resp:
            payload=json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        detail=e.read().decode('utf-8',errors='replace')
        if use_response_format and e.code in (400,404,422):
            return post_chat(base_url,api_key,model,system,prompt,timeout,False)
        raise RuntimeError(f'HTTP {e.code}: {detail[:1000]}') from e
    content=payload['choices'][0]['message']['content']
    return content,payload


def score_case(case: dict, pred: dict) -> tuple[bool|None,list[str]]:
    reasons=[]
    atomic=set(pred.get('atomic_skills') or [])
    level=case['benchmark_level']
    if level=='atomic':
        target=case['target_skill']; t=case['type']
        if t=='should_trigger':
            ok=target in atomic
            if not ok: reasons.append(f'missing target skill {target}')
            return ok,reasons
        if t=='should_not_trigger':
            ok=target not in atomic
            if not ok: reasons.append(f'should not select {target}')
            return ok,reasons
        return None,['edge_case is recorded but not auto-scored']

    ok=True
    if pred.get('route')!=case['expected_route']:
        ok=False; reasons.append(f"route={pred.get('route')} expected={case['expected_route']}")
    expected_atomic=set(case.get('expected_atomic') or [])
    missing=expected_atomic-atomic
    if missing:
        ok=False; reasons.append('missing atomic: '+','.join(sorted(missing)))
    if case.get('expected_framework') and pred.get('framework')!=case['expected_framework']:
        ok=False; reasons.append(f"framework={pred.get('framework')} expected={case['expected_framework']}")
    if case.get('expected_composite') and pred.get('composite')!=case['expected_composite']:
        ok=False; reasons.append(f"composite={pred.get('composite')} expected={case['expected_composite']}")
    components=set(pred.get('components') or [])
    missing_components=set(case.get('expected_components') or [])-components
    if missing_components:
        ok=False; reasons.append('missing components: '+','.join(sorted(missing_components)))
    return ok,reasons


def run_one(case: dict, args, system: str) -> dict:
    started=time.perf_counter()
    result={'id':case['id'],'benchmark_level':case['benchmark_level'],'type':case.get('type'),'prompt':case['prompt']}
    try:
        content,payload=post_chat(args.base_url,args.api_key,args.model,system,case['prompt'],args.timeout,not args.no_response_format)
        pred=parse_json_object(content)
        passed,reasons=score_case(case,pred)
        result.update({'prediction':pred,'passed':passed,'reasons':reasons,'latency_s':round(time.perf_counter()-started,3),'usage':payload.get('usage')})
    except Exception as e:
        result.update({'prediction':None,'passed':False,'reasons':[str(e)],'latency_s':round(time.perf_counter()-started,3),'error':type(e).__name__})
    return result


def summarize(results: list[dict]) -> dict:
    scored=[r for r in results if r.get('passed') is not None]
    passed=sum(r.get('passed') is True for r in scored)
    by_level={}
    for level in sorted({r['benchmark_level'] for r in results}):
        xs=[r for r in results if r['benchmark_level']==level and r.get('passed') is not None]
        by_level[level]={'scored':len(xs),'passed':sum(r.get('passed') is True for r in xs)}
        by_level[level]['pass_rate']=round(by_level[level]['passed']/len(xs),4) if xs else None
    by_type={}
    for case_type in sorted({r.get('type') for r in results if r.get('type')}):
        xs=[r for r in results if r.get('type')==case_type and r.get('passed') is not None]
        by_type[case_type]={
            'cases':sum(r.get('type')==case_type for r in results),
            'scored':len(xs),
            'passed':sum(r.get('passed') is True for r in xs),
            'pass_rate':round(sum(r.get('passed') is True for r in xs)/len(xs),4) if xs else None,
        }
    latencies=[r['latency_s'] for r in results if isinstance(r.get('latency_s'),(int,float))]
    token_totals=[(r.get('usage') or {}).get('total_tokens') for r in results]
    token_totals=[x for x in token_totals if isinstance(x,(int,float))]
    return {
        'cases_total':len(results),
        'scored':len(scored),
        'passed':passed,
        'pass_rate':round(passed/len(scored),4) if scored else None,
        'by_level':by_level,
        'by_type':by_type,
        'errors':sum(bool(r.get('error')) for r in results),
        'avg_latency_s':round(sum(latencies)/len(latencies),3) if latencies else None,
        'total_tokens':int(sum(token_totals)) if token_totals else None,
    }


def main() -> None:
    ap=argparse.ArgumentParser(description='Run the unified routing benchmark against an OpenAI-compatible chat/completions endpoint.')
    ap.add_argument('--base-url',default=os.getenv('MAOXUAN_BENCH_BASE_URL'))
    ap.add_argument('--api-key',default=os.getenv('MAOXUAN_BENCH_API_KEY'))
    ap.add_argument('--model',default=os.getenv('MAOXUAN_BENCH_MODEL'))
    ap.add_argument('--workers',type=int,default=4)
    ap.add_argument('--timeout',type=int,default=90)
    ap.add_argument('--limit',type=int)
    ap.add_argument('--output')
    ap.add_argument('--no-response-format',action='store_true')
    ap.add_argument('--dry-run',action='store_true',help='Validate and count the benchmark without making network calls.')
    args=ap.parse_args()
    cases=stratified_sample(load_cases(),args.limit)
    system=build_system_prompt()
    if args.dry_run:
        type_counts={}
        for c in cases:
            type_counts[c['type']]=type_counts.get(c['type'],0)+1
        print(json.dumps({'ok':True,'cases':len(cases),'system_prompt_chars':len(system),'atomic_cases':sum(c['benchmark_level']=='atomic' for c in cases),'system_router_cases':sum(c['benchmark_level']=='system_router' for c in cases),'by_type':type_counts},ensure_ascii=False,indent=2))
        return
    if not args.base_url or not args.model:
        ap.error('set --base-url/MAOXUAN_BENCH_BASE_URL and --model/MAOXUAN_BENCH_MODEL')
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,args.workers)) as ex:
        results=list(ex.map(lambda c:run_one(c,args,system),cases))
    summary=summarize(results)
    RESULTS_DIR.mkdir(parents=True,exist_ok=True)
    stamp=time.strftime('%Y%m%d-%H%M%S')
    out=Path(args.output) if args.output else RESULTS_DIR/f'router-{args.model.replace("/","_")}-{stamp}.jsonl'
    with out.open('w',encoding='utf-8') as f:
        for r in results: f.write(json.dumps(r,ensure_ascii=False)+'\n')
    summary_path=out.with_suffix('.summary.json')
    summary_path.write_text(json.dumps({'model':args.model,'base_url':args.base_url,'summary':summary},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print(out); print(summary_path)

if __name__=='__main__': main()
