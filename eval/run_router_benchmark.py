#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import difflib
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
ROUTING_PROFILES = ROOT / 'skills/atomic/ROUTING_PROFILES.json'
FRAMEWORKS = ROOT / 'skills/frameworks/FRAMEWORKS.json'
RESULTS_DIR = ROOT / 'eval/results'
ROUTES = {'direct', 'source_lookup', 'method_application', 'composite_task', 'mixed'}


def ensure_atomic_dataset() -> None:
    if not ATOMIC_DATASET.exists():
        subprocess.run([sys.executable, str(ROOT / 'eval/build_atomic_benchmark.py')], cwd=ROOT, check=True)


def load_cases() -> list[dict]:
    ensure_atomic_dataset()
    cases = []
    for line in ATOMIC_DATASET.read_text(encoding='utf-8').splitlines():
        if line.strip():
            item = json.loads(line)
            item['benchmark_level'] = 'atomic'
            cases.append(item)
    rt = json.loads(ROUTER_TESTS.read_text(encoding='utf-8'))
    for c in rt['cases']:
        cases.append({
            'id': f"system:{c['id']}",
            'benchmark_level': 'system_router',
            'type': 'system_router',
            'prompt': c['prompt'],
            'expected_route': c['expected_route'],
            'expected_framework': c.get('expected_framework'),
            'expected_atomic': c.get('expected_atomic', []),
            'expected_composite': c.get('expected_composite'),
            'expected_components': c.get('expected_components', []),
        })
    return cases


def _stable_rank(case: dict) -> str:
    return hashlib.sha256(case['id'].encode()).hexdigest()


def stratified_sample(cases: list[dict], limit: int | None) -> list[dict]:
    if not limit or limit >= len(cases):
        return cases
    if limit <= 0:
        return []
    buckets: dict[str, list[dict]] = {}
    for c in cases:
        buckets.setdefault(c.get('type') or 'unknown', []).append(c)
    total = sum(map(len, buckets.values()))
    raw = {k: limit * len(v) / total for k, v in buckets.items()}
    quota = {k: min(len(buckets[k]), math.floor(raw[k])) for k in buckets}
    remaining = limit - sum(quota.values())
    order = sorted(buckets, key=lambda k: (raw[k] - math.floor(raw[k]), len(buckets[k]), k), reverse=True)
    while remaining:
        moved = False
        for k in order:
            if quota[k] < len(buckets[k]):
                quota[k] += 1
                remaining -= 1
                moved = True
                if not remaining:
                    break
        if not moved:
            break
    selected = []
    for k, items in buckets.items():
        selected.extend(sorted(items, key=_stable_rank)[:quota[k]])
    return sorted(selected, key=lambda c: c['id'])


def load_schema() -> dict:
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    profiles_doc = json.loads(ROUTING_PROFILES.read_text(encoding='utf-8'))
    fw = json.loads(FRAMEWORKS.read_text(encoding='utf-8'))
    composites = [p.parent.name for p in sorted((ROOT / 'skills/composite').glob('*/SKILL.md'))]
    profiles = {x['slug']: x for x in profiles_doc['profiles']}
    slugs = {x['slug'] for x in catalog['skills']}
    if set(profiles) != slugs:
        missing = sorted(slugs - set(profiles))
        extra = sorted(set(profiles) - slugs)
        raise ValueError(f'ROUTING_PROFILES/CATALOG mismatch missing={missing} extra={extra}')
    return {
        'catalog': catalog,
        'profiles_doc': profiles_doc,
        'profiles': profiles,
        'frameworks': fw,
        'composites': set(composites),
        'slugs': slugs,
        'framework_ids': {x['id'] for x in fw['frameworks']},
    }


def build_system_prompt(schema: dict) -> str:
    skill_lines = [f"- {x['slug']} ({x['name']}): {x['summary']}" for x in schema['catalog']['skills']]
    profile_lines = [
        f"- {slug} | WHEN: {p['when']} | AVOID: {p['avoid']} | CONTRAST: {p['contrast']}"
        for slug, p in schema['profiles'].items()
    ]
    framework_lines = [f"- {x['id']}: {', '.join(x['atomic_skills'])}" for x in schema['frameworks']['frameworks']]
    composites = ', '.join(sorted(schema['composites']))
    specificity = schema['profiles_doc'].get('policy', {}).get('specificity_rule', '')
    direct_default = schema['profiles_doc'].get('policy', {}).get('direct_default', '')
    return f"""You are the routing evaluator for a layered Selected Works methodology skill system.
Classify the user's request; do not answer the substantive question.

First apply a skill-necessity gate. Default to direct when this special methodology system does not materially improve the task.
Do NOT select a methodology skill merely because the user has a problem, decision, disagreement, bug, or learning request.
Profile policy: {direct_default}

Routes:
- direct: no Selected Works retrieval or methodology skill is needed.
- source_lookup: original text, citation, article meaning, textual/historical explanation. components MUST include \"retrieval\".
- method_application: a focused non-political problem where one framework and 1-4 atomic skills materially improve analysis.
- composite_task: a genuinely multi-stage non-political task needing an end-to-end named composite workflow, not merely a task where several atomic skills are relevant.
- mixed: both original-source evidence and method application are materially required; components MUST include \"retrieval\".

Route promotion rule:
- Prefer method_application when one focused mechanism or a small atomic set is sufficient.
- Promote to composite_task only when the user asks for an end-to-end analysis/plan spanning multiple distinct stages or workstreams and a named composite matches the requested workflow.
- Do not promote merely because the situation is important, unfamiliar, or could benefit from several techniques.

Use direct for ordinary tutorials, routine verification/calculation, a single well-scoped implementation bug, aesthetic/formatting choices, and one-off preferences unless deeper methodology is materially useful.
Choose the smallest sufficient set. Never invent or alter a slug. Select at most 4 atomic skills.

Atomic skills and summaries:
{chr(10).join(skill_lines)}

Atomic routing profiles (authoritative applicability boundaries):
{chr(10).join(profile_lines)}

Specificity policy:
{specificity}
When a specialized mechanism and a generic analytical skill both fit, include the specialized mechanism first. Generic skills such as maodun-fenxi, maodun-techuxing, neiyin-juedinglun, and bianzheng-pingheng should supplement rather than displace a more specific mechanism.

Framework -> atomic map:
{chr(10).join(framework_lines)}
Composite workflows: {composites}

Political neutrality boundary: for current politics, elections, parties, officials, legislation, ballot measures, or political persuasion, do not route into strategic persuasion/action skills. Source lookup and neutral factual comparison are allowed.
Historical military-origin skills may only be routed for explicitly non-violent domains such as product, engineering, research, project management, organizational learning, or lawful business competition.

Return JSON only:
{{"route":"direct|source_lookup|method_application|composite_task|mixed","framework":null,"atomic_skills":[],"composite":null,"components":[]}}
route must be exactly ONE enum value, never the enum expression itself. Do not include prose outside JSON."""


def parse_json_object(text: str) -> dict:
    text = text.strip()
    if text.startswith('```'):
        text = text.strip('`').strip()
        if text.lower().startswith('json'):
            text = text[4:].strip()
    try:
        v = json.loads(text)
        if isinstance(v, dict):
            return v
    except json.JSONDecodeError:
        pass
    dec = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch != '{':
            continue
        try:
            v, _ = dec.raw_decode(text[i:])
            if isinstance(v, dict):
                return v
        except json.JSONDecodeError:
            continue
    raise ValueError('model output does not contain a JSON object')


def post_chat(base_url: str, api_key: str | None, model: str, system: str, prompt: str, timeout: int, use_response_format: bool) -> tuple[str, dict]:
    url = base_url.rstrip('/') + '/chat/completions'
    body = {
        'model': model,
        'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': prompt}],
        'temperature': 0,
    }
    if use_response_format:
        body['response_format'] = {'type': 'json_object'}
    req = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={'Content-Type': 'application/json', **({'Authorization': 'Bearer ' + api_key} if api_key else {})},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors='replace')
        if use_response_format and e.code in (400, 404, 422):
            return post_chat(base_url, api_key, model, system, prompt, timeout, False)
        raise RuntimeError(f'HTTP {e.code}: {detail[:1000]}') from e
    return payload['choices'][0]['message']['content'], payload


def _near_slug(value: str, allowed: set[str]) -> str | None:
    scored = sorted(((difflib.SequenceMatcher(None, value, x).ratio(), x) for x in allowed), reverse=True)
    if not scored or scored[0][0] < .92:
        return None
    if len(scored) > 1 and scored[0][0] - scored[1][0] < .04:
        return None
    return scored[0][1]


def normalize_validate(pred: dict, schema: dict) -> tuple[dict, list[str], list[str]]:
    out = {
        'route': pred.get('route'),
        'framework': pred.get('framework'),
        'atomic_skills': pred.get('atomic_skills') if isinstance(pred.get('atomic_skills'), list) else [],
        'composite': pred.get('composite'),
        'components': pred.get('components') if isinstance(pred.get('components'), list) else [],
    }
    corrections = []
    errors = []
    atoms = []
    for raw in out['atomic_skills']:
        if not isinstance(raw, str):
            errors.append('atomic skill must be a string')
            continue
        if raw in schema['slugs']:
            atoms.append(raw)
            continue
        fixed = _near_slug(raw, schema['slugs'])
        if fixed:
            atoms.append(fixed)
            corrections.append(f'atomic:{raw}->{fixed}')
        else:
            errors.append(f'unknown atomic skill {raw}')
    out['atomic_skills'] = list(dict.fromkeys(atoms))
    if out['route'] not in ROUTES:
        errors.append(f"invalid route {out['route']}")
    if out['framework'] is not None and out['framework'] not in schema['framework_ids']:
        errors.append(f"unknown framework {out['framework']}")
    if out['composite'] is not None and out['composite'] not in schema['composites']:
        errors.append(f"unknown composite {out['composite']}")
    if len(out['atomic_skills']) > 4:
        errors.append('more than 4 atomic skills')
    if out['route'] in {'direct', 'source_lookup'} and out['atomic_skills']:
        errors.append(f"{out['route']} must not select atomic skills")
    if out['route'] == 'composite_task' and not out['composite']:
        errors.append('composite_task requires composite')
    if out['route'] == 'method_application' and out['composite'] is not None:
        errors.append('method_application must not set composite')
    return out, corrections, errors


def usage_total(payloads: list[dict]) -> dict | None:
    usages = [p.get('usage') or {} for p in payloads]
    keys = {'prompt_tokens', 'completion_tokens', 'total_tokens'}
    result = {k: sum(u.get(k, 0) or 0 for u in usages) for k in keys}
    return result if any(result.values()) else None


def score_case(case: dict, pred: dict, validation_errors: list[str]) -> tuple[bool | None, list[str]]:
    if validation_errors:
        return False, ['schema: ' + x for x in validation_errors]
    reasons = []
    atomic = set(pred.get('atomic_skills') or [])
    if case['benchmark_level'] == 'atomic':
        target = case['target_skill']
        t = case['type']
        if t == 'should_trigger':
            ok = target in atomic
            return ok, ([] if ok else [f'missing target skill {target}'])
        if t == 'should_not_trigger':
            ok = target not in atomic
            return ok, ([] if ok else [f'should not select {target}'])
        return None, ['edge_case is recorded but not auto-scored']
    ok = True
    if pred.get('route') != case['expected_route']:
        ok = False
        reasons.append(f"route={pred.get('route')} expected={case['expected_route']}")
    missing = set(case.get('expected_atomic') or []) - atomic
    if missing:
        ok = False
        reasons.append('missing atomic: ' + ','.join(sorted(missing)))
    if case.get('expected_framework') and pred.get('framework') != case['expected_framework']:
        ok = False
        reasons.append(f"framework={pred.get('framework')} expected={case['expected_framework']}")
    if case.get('expected_composite') and pred.get('composite') != case['expected_composite']:
        ok = False
        reasons.append(f"composite={pred.get('composite')} expected={case['expected_composite']}")
    components = set(pred.get('components') or [])
    if pred.get('route') in {'source_lookup', 'mixed'}:
        components.add('retrieval')
    missing_components = set(case.get('expected_components') or []) - components
    if missing_components:
        ok = False
        reasons.append('missing components: ' + ','.join(sorted(missing_components)))
    return ok, reasons


def _repair_prompt(case_prompt: str, problem: str, previous: str) -> str:
    return (
        case_prompt
        + '\n\nYour previous routing output was invalid. Fix ONLY the routing JSON.'
        + '\nProblem: ' + problem
        + '\nPrevious output: ' + previous[:4000]
        + '\nReturn corrected JSON only.'
    )


def run_one(case: dict, args, system: str, schema: dict) -> dict:
    started = time.perf_counter()
    payloads = []
    repair_attempted = False
    result = {'id': case['id'], 'benchmark_level': case['benchmark_level'], 'type': case.get('type'), 'prompt': case['prompt']}
    try:
        content, payload = post_chat(args.base_url, args.api_key, args.model, system, case['prompt'], args.timeout, not args.no_response_format)
        payloads.append(payload)
        try:
            raw = parse_json_object(content)
        except ValueError as parse_error:
            repair_attempted = True
            repair = _repair_prompt(case['prompt'], str(parse_error), content)
            content2, payload2 = post_chat(args.base_url, args.api_key, args.model, system, repair, args.timeout, not args.no_response_format)
            payloads.append(payload2)
            raw = parse_json_object(content2)
        pred, corrections, errors = normalize_validate(raw, schema)
        first_errors = list(errors)
        if errors:
            repair_attempted = True
            repair = _repair_prompt(case['prompt'], json.dumps(errors, ensure_ascii=False), json.dumps(raw, ensure_ascii=False))
            content2, payload2 = post_chat(args.base_url, args.api_key, args.model, system, repair, args.timeout, not args.no_response_format)
            payloads.append(payload2)
            raw2 = parse_json_object(content2)
            pred2, corr2, errors2 = normalize_validate(raw2, schema)
            raw, pred, corrections, errors = raw2, pred2, corrections + corr2, errors2
        passed, reasons = score_case(case, pred, errors)
        result.update({
            'raw_prediction': raw,
            'prediction': pred,
            'passed': passed,
            'reasons': reasons,
            'validation_errors': errors,
            'initial_validation_errors': first_errors,
            'corrections': corrections,
            'repair_attempted': repair_attempted,
            'latency_s': round(time.perf_counter() - started, 3),
            'usage': usage_total(payloads),
        })
    except Exception as e:
        result.update({
            'prediction': None,
            'passed': False,
            'reasons': [str(e)],
            'latency_s': round(time.perf_counter() - started, 3),
            'error': type(e).__name__,
            'repair_attempted': repair_attempted,
            'usage': usage_total(payloads),
        })
    return result


def summarize(results: list[dict]) -> dict:
    scored = [r for r in results if r.get('passed') is not None]
    passed = sum(r.get('passed') is True for r in scored)
    by_level = {}
    by_type = {}
    for level in sorted({r['benchmark_level'] for r in results}):
        xs = [r for r in results if r['benchmark_level'] == level and r.get('passed') is not None]
        by_level[level] = {
            'scored': len(xs),
            'passed': sum(r.get('passed') is True for r in xs),
            'pass_rate': round(sum(r.get('passed') is True for r in xs) / len(xs), 4) if xs else None,
        }
    for t in sorted({r.get('type') for r in results if r.get('type')}):
        xs = [r for r in results if r.get('type') == t and r.get('passed') is not None]
        by_type[t] = {
            'cases': sum(r.get('type') == t for r in results),
            'scored': len(xs),
            'passed': sum(r.get('passed') is True for r in xs),
            'pass_rate': round(sum(r.get('passed') is True for r in xs) / len(xs), 4) if xs else None,
        }
    lats = [r['latency_s'] for r in results if isinstance(r.get('latency_s'), (int, float))]
    toks = [(r.get('usage') or {}).get('total_tokens') for r in results]
    toks = [x for x in toks if isinstance(x, (int, float))]
    return {
        'cases_total': len(results),
        'scored': len(scored),
        'passed': passed,
        'pass_rate': round(passed / len(scored), 4) if scored else None,
        'by_level': by_level,
        'by_type': by_type,
        'errors': sum(bool(r.get('error')) for r in results),
        'repairs': sum(bool(r.get('repair_attempted')) for r in results),
        'normalizations': sum(bool(r.get('corrections')) for r in results),
        'avg_latency_s': round(sum(lats) / len(lats), 3) if lats else None,
        'total_tokens': int(sum(toks)) if toks else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description='Run unified routing benchmark against an OpenAI-compatible endpoint.')
    ap.add_argument('--base-url', default=os.getenv('MAOXUAN_BENCH_BASE_URL'))
    ap.add_argument('--api-key', default=os.getenv('MAOXUAN_BENCH_API_KEY'))
    ap.add_argument('--model', default=os.getenv('MAOXUAN_BENCH_MODEL'))
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--timeout', type=int, default=90)
    ap.add_argument('--limit', type=int)
    ap.add_argument('--output')
    ap.add_argument('--no-response-format', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    cases = stratified_sample(load_cases(), args.limit)
    schema = load_schema()
    system = build_system_prompt(schema)
    if args.dry_run:
        counts = {}
        for c in cases:
            counts[c['type']] = counts.get(c['type'], 0) + 1
        print(json.dumps({
            'ok': True,
            'cases': len(cases),
            'system_prompt_chars': len(system),
            'routing_profiles': len(schema['profiles']),
            'atomic_cases': sum(c['benchmark_level'] == 'atomic' for c in cases),
            'system_router_cases': sum(c['benchmark_level'] == 'system_router' for c in cases),
            'by_type': counts,
        }, ensure_ascii=False, indent=2))
        return
    if not args.base_url or not args.model:
        ap.error('set --base-url and --model')
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        results = list(ex.map(lambda c: run_one(c, args, system, schema), cases))
    summary = summarize(results)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%Y%m%d-%H%M%S')
    out = Path(args.output) if args.output else RESULTS_DIR / f'router-{args.model.replace("/", "_")}-{stamp}.jsonl'
    with out.open('w', encoding='utf-8') as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    summary_path = out.with_suffix('.summary.json')
    summary_path.write_text(json.dumps({'model': args.model, 'base_url': args.base_url, 'summary': summary}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(out)
    print(summary_path)


if __name__ == '__main__':
    main()
