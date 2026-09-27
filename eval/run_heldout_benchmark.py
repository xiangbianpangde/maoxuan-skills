#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / 'eval'
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

import run_router_benchmark as rb  # noqa: E402

DATASET = ROOT / 'eval/heldout/router-heldout-v1.jsonl'
RESULTS_DIR = ROOT / 'eval/results'


def load_cases() -> list[dict]:
    cases = []
    for line in DATASET.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        c['benchmark_level'] = 'heldout'
        c['type'] = c['category']
        cases.append(c)
    ids = [c['id'] for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError('held-out case IDs must be unique')
    return cases


def heldout_score(case: dict, pred: dict, validation_errors: list[str]):
    if validation_errors:
        return False, ['schema: ' + x for x in validation_errors]
    reasons: list[str] = []
    atomic = set(pred.get('atomic_skills') or [])
    expected_route = case.get('expected_route')
    if expected_route and pred.get('route') != expected_route:
        reasons.append(f"route={pred.get('route')} expected={expected_route}")
    missing = set(case.get('required_atomic') or []) - atomic
    if missing:
        reasons.append('missing atomic: ' + ','.join(sorted(missing)))
    forbidden = set(case.get('forbidden_atomic') or []) & atomic
    if forbidden:
        reasons.append('forbidden atomic: ' + ','.join(sorted(forbidden)))
    expected_framework = case.get('expected_framework')
    if expected_framework and pred.get('framework') != expected_framework:
        reasons.append(f"framework={pred.get('framework')} expected={expected_framework}")
    expected_composite = case.get('expected_composite')
    if expected_composite and pred.get('composite') != expected_composite:
        reasons.append(f"composite={pred.get('composite')} expected={expected_composite}")
    components = set(pred.get('components') or [])
    if pred.get('route') in {'source_lookup', 'mixed'}:
        components.add('retrieval')
    missing_components = set(case.get('expected_components') or []) - components
    if missing_components:
        reasons.append('missing components: ' + ','.join(sorted(missing_components)))
    return not reasons, reasons


def build_catalog_single_prompt(schema: dict) -> str:
    skill_lines = [
        f"- {x['slug']} [{x['group']}] {x['name']}: {x['summary']}"
        for x in schema['catalog']['skills']
    ]
    framework_lines = [
        f"- {fid}: {f['purpose']} | atomic={','.join(f['atomic_skills'])}"
        for fid, f in schema['frameworks'].items()
    ]
    composite_lines = [
        f"- {cid}: {rb.COMPOSITE_HINTS.get(cid, cid)}"
        for cid in sorted(schema['composites'])
    ]
    return f"""You are a single-stage router for a layered Selected Works methodology skill system.
Classify the user's request; do not answer the substantive question.

First apply a skill-necessity gate. Default to direct when this methodology system does not materially improve the task.
Do not choose methodology Skills merely because the user has a problem, bug, disagreement, preference, tutorial request, routine calculation, formatting request, or ordinary implementation question.

Routes:
- direct: no source retrieval or methodology Skill is materially needed.
- source_lookup: original text, citation, article meaning, textual/historical explanation; components must include \"retrieval\".
- method_application: focused non-political problem where 1-4 atomic Skills materially improve analysis.
- composite_task: genuinely multi-stage/end-to-end work matching a named composite workflow.
- mixed: source evidence and method application are both materially required; components must include \"retrieval\".

Promotion rules:
- Prefer method_application for one focused mechanism or a small atomic set.
- Use composite_task only for a request that explicitly spans multiple distinct stages/workstreams and matches a named composite.
- Choose the smallest sufficient set, at most 4 atomic Skills.
- Specialized mechanisms should be selected instead of generic analytical Skills when both fit directly.
- Never invent or alter an ID.

Atomic Skill catalog:
{chr(10).join(skill_lines)}

Frameworks:
{chr(10).join(framework_lines)}

Composite workflows:
{chr(10).join(composite_lines)}

Political neutrality boundary:
- Current politics, elections, parties, officials, legislation, ballot measures, political persuasion or voter mobilization must not be routed into strategic action/persuasion methodology Skills.
- Neutral source/factual analysis is allowed.
- Military-origin methods may only be abstracted to explicit non-violent domains such as engineering, research, product, project management, organizational learning, or lawful business competition.

Return JSON only:
{{\"route\":\"direct|source_lookup|method_application|composite_task|mixed\",\"framework\":null,\"atomic_skills\":[],\"composite\":null,\"components\":[]}}
"""


def run_one_catalog(case: dict, args, system: str, schema: dict) -> dict:
    started = time.perf_counter()
    payloads: list[dict] = []
    result = {
        'id': case['id'],
        'benchmark_level': 'heldout',
        'type': case['category'],
        'prompt': case['prompt'],
        'architecture': 'catalog-single',
    }
    try:
        pred, corrections, errors, repaired, meta = rb._call_and_normalize(
            case['prompt'], args, system,
            lambda raw: rb.normalize_final(raw, schema),
            payloads,
        )
        passed, reasons = heldout_score(case, pred, errors)
        result.update({
            'raw_prediction': meta['raw'],
            'prediction': pred,
            'passed': passed,
            'reasons': reasons,
            'validation_errors': errors,
            'initial_validation_errors': meta['initial_errors'],
            'corrections': corrections,
            'repair_attempted': repaired,
            'repair_count': int(repaired),
            'stage_calls': len(payloads),
            'latency_s': round(time.perf_counter() - started, 3),
            'usage': rb.usage_total(payloads),
        })
    except Exception as e:
        result.update({
            'prediction': None,
            'passed': False,
            'reasons': [str(e)],
            'error': type(e).__name__,
            'repair_attempted': False,
            'repair_count': 0,
            'stage_calls': len(payloads),
            'latency_s': round(time.perf_counter() - started, 3),
            'usage': rb.usage_total(payloads),
        })
    return result


def summarize(results: list[dict], architecture: str) -> dict:
    passed = sum(r.get('passed') is True for r in results)
    by_category = {}
    for cat in sorted({r['type'] for r in results}):
        xs = [r for r in results if r['type'] == cat]
        p = sum(r.get('passed') is True for r in xs)
        by_category[cat] = {'cases': len(xs), 'passed': p, 'pass_rate': round(p / len(xs), 4)}
    lats = [r['latency_s'] for r in results if isinstance(r.get('latency_s'), (int, float))]
    toks = [(r.get('usage') or {}).get('total_tokens') for r in results]
    toks = [x for x in toks if isinstance(x, (int, float))]
    stage_calls = [r.get('stage_calls') for r in results if isinstance(r.get('stage_calls'), (int, float))]
    pools = [len(r.get('candidate_pool') or []) for r in results if r.get('stage2_used')]
    return {
        'suite': 'router-heldout-v1',
        'architecture': architecture,
        'cases_total': len(results),
        'passed': passed,
        'pass_rate': round(passed / len(results), 4) if results else None,
        'by_category': by_category,
        'errors': sum(bool(r.get('error')) for r in results),
        'repairs': sum(bool(r.get('repair_attempted')) for r in results),
        'normalizations': sum(bool(r.get('corrections')) for r in results),
        'avg_stage_calls': round(sum(stage_calls) / len(stage_calls), 3) if stage_calls else None,
        'avg_candidate_pool': round(sum(pools) / len(pools), 3) if pools else None,
        'avg_latency_s': round(sum(lats) / len(lats), 3) if lats else None,
        'total_tokens': int(sum(toks)) if toks else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description='One-shot held-out router benchmark.')
    ap.add_argument('--architecture', choices=['catalog-single', 'two-stage-v5'], required=True)
    ap.add_argument('--base-url', default=os.getenv('MAOXUAN_BENCH_BASE_URL'))
    ap.add_argument('--api-key', default=os.getenv('MAOXUAN_BENCH_API_KEY'))
    ap.add_argument('--model', default=os.getenv('MAOXUAN_BENCH_MODEL'))
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--timeout', type=int, default=90)
    ap.add_argument('--output')
    ap.add_argument('--no-response-format', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    cases = load_cases()
    schema = rb.load_schema()
    if args.architecture == 'catalog-single':
        system = build_catalog_single_prompt(schema)
    else:
        system = rb.build_stage1_prompt(schema)

    if args.dry_run:
        counts = {}
        for c in cases:
            counts[c['category']] = counts.get(c['category'], 0) + 1
        print(json.dumps({
            'ok': True,
            'suite': 'router-heldout-v1',
            'architecture': args.architecture,
            'cases': len(cases),
            'system_prompt_chars': len(system),
            'by_category': counts,
        }, ensure_ascii=False, indent=2))
        return

    if not args.base_url or not args.model:
        ap.error('set --base-url and --model')

    old_score = rb.score_case
    rb.score_case = heldout_score
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
            if args.architecture == 'catalog-single':
                results = list(ex.map(lambda c: run_one_catalog(c, args, system, schema), cases))
            else:
                results = list(ex.map(lambda c: rb.run_one(c, args, system, schema), cases))
    finally:
        rb.score_case = old_score

    summary = summarize(results, args.architecture)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = Path(args.output) if args.output else RESULTS_DIR / f'heldout-{args.architecture}-{args.model.replace("/", "_")}.jsonl'
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
