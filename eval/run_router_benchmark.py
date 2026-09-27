#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import json
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


def build_system_prompt() -> str:
    catalog=json.loads(CATALOG.read_text(encoding='utf-8'))
    fw=json.loads(FRAMEWORKS.read_text(encoding='utf-8'))
    slugs=[x['slug'] for x in catalog['skills']]
    framework_lines=[f"- {x['id']}: {', '.join(x['atomic_skills'])}" for x in fw['frameworks']]
    composites=[p.parent.name for p in sorted((ROOT/'skills/composite').glob('*/SKILL.md'))]
    return f"""You are the routing evaluator for a layered Selected Works methodology skill system.
Classify the user's request; do not answer the substantive question.

Routes:
- source_lookup: original text, citation, article meaning, textual/historical explanation. Use component retrieval.
- method_application: a focused non-political problem where one framework and 1-4 atomic skills are enough.
- composite_task: a multi-stage non-political analysis requiring a composite workflow.
- mixed: both original-source evidence and method application are materially required.

Atomic skill slugs (choose only when genuinely applicable):
{', '.join(slugs)}

Framework -> atomic map:
{chr(10).join(framework_lines)}

Composite workflows: {', '.join(composites)}

Political neutrality boundary: for current politics, elections, parties, officials, legislation, ballot measures, or political persuasion, do not route into strategic persuasion/action skills. Source lookup and neutral factual comparison are allowed.
Historical military-origin skills may only be routed for explicitly non-violent domains such as product, engineering, research, project management, organizational learning, or lawful business competition.

Return JSON only with this schema:
{{"route":"source_lookup|method_application|composite_task|mixed","framework":null,"atomic_skills":[],"composite":null,"components":[]}}
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
    return {'cases_total':len(results),'scored':len(scored),'passed':passed,'pass_rate':round(passed/len(scored),4) if scored else None,'by_level':by_level,'errors':sum(bool(r.get('error')) for r in results)}


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
    cases=load_cases()
    if args.limit: cases=cases[:args.limit]
    system=build_system_prompt()
    if args.dry_run:
        print(json.dumps({'ok':True,'cases':len(cases),'system_prompt_chars':len(system),'atomic_cases':sum(c['benchmark_level']=='atomic' for c in cases),'system_router_cases':sum(c['benchmark_level']=='system_router' for c in cases)},ensure_ascii=False,indent=2))
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
