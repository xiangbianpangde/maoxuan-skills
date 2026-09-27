#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import difflib
import hashlib
import json
import math
import os
import re
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
GROUP_HINTS = {
    'cognition': '问题性质、主要矛盾、内外因、信息加工与认知判断',
    'research': '调查取证、一线反馈、事实补全与反馈闭环',
    'strategy': '非暴力竞争、长期阶段、资源集中、差异化与局部突破',
    'action': '行动学习、认知重启、执行主动性、长期信心与短期严谨',
    'organization': '组织冲突、纠偏、试点推广、合作边界、多任务协调与沟通',
}
COMPOSITE_HINTS = {
    'complex-problem-solving': '多问题、多阶段的端到端诊断、排序、验证与调整流程',
    'research-and-decision': '从调查取证、信息加工到判断和实践验证的完整决策流程',
    'strategy-analysis': '仅用于非暴力场景的多阶段战略分析、切入点与资源配置流程',
    'organization-improvement': '组织问题的反馈、分类、根因、纠偏、试点与推广流程',
}


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
    fw_doc = json.loads(FRAMEWORKS.read_text(encoding='utf-8'))
    composites = {p.parent.name for p in sorted((ROOT / 'skills/composite').glob('*/SKILL.md'))}
    skills = {x['slug']: x for x in catalog['skills']}
    profiles = {x['slug']: x for x in profiles_doc['profiles']}
    frameworks = {x['id']: x for x in fw_doc['frameworks']}
    if set(profiles) != set(skills):
        missing = sorted(set(skills) - set(profiles))
        extra = sorted(set(profiles) - set(skills))
        raise ValueError(f'ROUTING_PROFILES/CATALOG mismatch missing={missing} extra={extra}')
    groups: dict[str, list[str]] = {}
    for x in catalog['skills']:
        groups.setdefault(x['group'], []).append(x['slug'])
    unknown_groups = set(groups) - set(GROUP_HINTS)
    if unknown_groups:
        raise ValueError(f'unknown catalog groups: {sorted(unknown_groups)}')
    return {
        'catalog': catalog,
        'skills': skills,
        'profiles_doc': profiles_doc,
        'profiles': profiles,
        'frameworks_doc': fw_doc,
        'frameworks': frameworks,
        'composites': composites,
        'slugs': set(skills),
        'groups': groups,
        'group_ids': set(groups),
        'framework_ids': set(frameworks),
    }


def build_stage1_prompt(schema: dict) -> str:
    skill_lines = [
        f"- {x['slug']} [{x['group']}] {x['name']}: {x['summary']}"
        for x in schema['catalog']['skills']
    ]
    group_lines = [f"- {g}: {GROUP_HINTS[g]}" for g in schema['groups']]
    framework_lines = [
        f"- {fid}: {f['purpose']}"
        for fid, f in schema['frameworks'].items()
    ]
    composite_lines = [
        f"- {cid}: {COMPOSITE_HINTS.get(cid, cid)}"
        for cid in sorted(schema['composites'])
    ]
    return f"""You are Stage 1 (coarse router) for a layered Selected Works methodology skill system.
Classify the request and shortlist candidates. Do NOT answer the substantive question.

First apply a skill-necessity gate. Default to direct when this methodology system does not materially improve the task.
Do not select a methodology route merely because the user has a problem, bug, disagreement, preference, or learning request.

Routes:
- direct: ordinary task; no source retrieval or methodology Skill is materially needed.
- source_lookup: original text, citation, article meaning, textual/historical explanation. components must include \"retrieval\".
- method_application: a focused non-political problem where a small set of methods materially improves analysis.
- composite_task: genuinely end-to-end or multi-stage work matching one named composite workflow.
- mixed: both source evidence and method application are materially required. components must include \"retrieval\".

Promotion rule:
- Prefer method_application for one focused mechanism or a small atomic set.
- Use composite_task only for a request spanning multiple distinct stages/workstreams and matching a named composite.
- Do not use composite_task merely because a task is important or complex.

Skill groups:
{chr(10).join(group_lines)}

Atomic Skill catalog (short summaries only):
{chr(10).join(skill_lines)}

Frameworks:
{chr(10).join(framework_lines)}

Composite workflows:
{chr(10).join(composite_lines)}

Shortlisting rules:
- candidate_groups: at most 2 groups.
- candidate_skills: at most 6 atomic slugs most likely to contain the final answer. Prefer recall over exact ordering.
- framework_candidates: at most 2 framework IDs.
- For direct/source_lookup, candidate_groups/candidate_skills/framework_candidates must be empty.
- Never invent or alter IDs.

Political neutrality boundary:
- Current politics, elections, parties, officials, legislation, ballot measures, or political persuasion must not enter strategic persuasion/action methods.
- Neutral factual/source analysis is allowed.
- Military-origin methods may only be abstracted to explicit non-violent domains such as engineering, research, product, project management, organizational learning, or lawful business competition.

Return JSON only:
{{\"route\":\"direct|source_lookup|method_application|composite_task|mixed\",\"candidate_groups\":[],\"candidate_skills\":[],\"framework_candidates\":[],\"composite\":null,\"components\":[]}}
"""


def _candidate_profile_line(slug: str, schema: dict) -> str:
    s = schema['skills'][slug]
    p = schema['profiles'][slug]
    return (
        f"- {slug} ({s['name']}) [{s['group']}]\n"
        f"  SUMMARY: {s['summary']}\n"
        f"  WHEN: {p['when']}\n"
        f"  AVOID: {p['avoid']}\n"
        f"  CONTRAST: {p['contrast']}"
    )


def build_stage2_prompt(schema: dict, coarse: dict, candidates: list[str]) -> str:
    profile_lines = [_candidate_profile_line(slug, schema) for slug in candidates]
    framework_lines = [
        f"- {fid}: {f['purpose']} | atomic={','.join(f['atomic_skills'])}"
        for fid, f in schema['frameworks'].items()
    ]
    composite_lines = [
        f"- {cid}: {COMPOSITE_HINTS.get(cid, cid)}"
        for cid in sorted(schema['composites'])
    ]
    specificity = schema['profiles_doc'].get('policy', {}).get('specificity_rule', '')
    return f"""You are Stage 2 (fine router) for a layered Selected Works methodology skill system.
Do NOT answer the substantive question. Produce the final routing JSON.

Stage 1 decision:
{json.dumps(coarse, ensure_ascii=False)}

Only the following Atomic Skills are eligible in this fine-routing pass:
{chr(10).join(profile_lines)}

Rules:
- Select 1-4 Atomic Skills only from the eligible list, and only when each materially helps.
- Specialized mechanisms outrank generic analytical Skills.
- {specificity}
- Keep the Stage 1 route unless the detailed candidate boundaries clearly show it is wrong.
- method_application is preferred for a focused problem.
- composite_task is only for a genuinely multi-stage/end-to-end workflow, not merely because multiple atomic Skills are relevant.
- If route is direct or source_lookup, atomic_skills must be empty.
- source_lookup and mixed must include \"retrieval\" in components.

Frameworks (you may choose the best one or null):
{chr(10).join(framework_lines)}

Composite workflows:
{chr(10).join(composite_lines)}

Political neutrality boundary:
- Do not convert current politics/elections/parties/officials/legislation/political persuasion into strategic action advice.
- Neutral source/factual analysis is allowed.
- Military-origin methods are limited to explicit non-violent abstraction.

Return JSON only:
{{\"route\":\"direct|source_lookup|method_application|composite_task|mixed\",\"framework\":null,\"atomic_skills\":[],\"composite\":null,\"components\":[]}}
"""


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


def _near_value(value: str, allowed: set[str], threshold: float = .92) -> str | None:
    scored = sorted(((difflib.SequenceMatcher(None, value, x).ratio(), x) for x in allowed), reverse=True)
    if not scored or scored[0][0] < threshold:
        return None
    if len(scored) > 1 and scored[0][0] - scored[1][0] < .04:
        return None
    return scored[0][1]


def _normalize_string_list(values, allowed: set[str], label: str, max_items: int, corrections: list[str], errors: list[str]) -> list[str]:
    if not isinstance(values, list):
        errors.append(f'{label} must be a list')
        return []
    out = []
    for raw in values:
        if not isinstance(raw, str):
            errors.append(f'{label} item must be a string')
            continue
        if raw in allowed:
            out.append(raw)
            continue
        fixed = _near_value(raw, allowed)
        if fixed:
            out.append(fixed)
            corrections.append(f'{label}:{raw}->{fixed}')
        else:
            errors.append(f'unknown {label} {raw}')
    out = list(dict.fromkeys(out))
    if len(out) > max_items:
        errors.append(f'{label} has more than {max_items} items')
    return out[:max_items]


def normalize_stage1(pred: dict, schema: dict) -> tuple[dict, list[str], list[str]]:
    corrections: list[str] = []
    errors: list[str] = []
    route = pred.get('route')
    if route not in ROUTES:
        errors.append(f'invalid route {route}')
    groups = _normalize_string_list(pred.get('candidate_groups', []), schema['group_ids'], 'candidate_group', 2, corrections, errors)
    skills = _normalize_string_list(pred.get('candidate_skills', []), schema['slugs'], 'candidate_skill', 6, corrections, errors)
    fws = _normalize_string_list(pred.get('framework_candidates', []), schema['framework_ids'], 'framework_candidate', 2, corrections, errors)
    composite = pred.get('composite')
    if composite is not None and composite not in schema['composites']:
        fixed = _near_value(composite, schema['composites'])
        if fixed:
            corrections.append(f'composite:{composite}->{fixed}')
            composite = fixed
        else:
            errors.append(f'unknown composite {composite}')
    components = pred.get('components') if isinstance(pred.get('components'), list) else []
    components = [x for x in components if isinstance(x, str)]
    out = {
        'route': route,
        'candidate_groups': groups,
        'candidate_skills': skills,
        'framework_candidates': fws,
        'composite': composite,
        'components': list(dict.fromkeys(components)),
    }
    if route in {'direct', 'source_lookup'}:
        if groups or skills or fws:
            corrections.append('cleared methodology candidates for non-method route')
        out['candidate_groups'] = []
        out['candidate_skills'] = []
        out['framework_candidates'] = []
        out['composite'] = None
    elif route in {'method_application', 'mixed', 'composite_task'} and not (groups or skills or fws):
        errors.append('method route requires at least one candidate group/skill/framework')
    if route == 'composite_task' and not composite:
        errors.append('composite_task requires composite')
    if route == 'method_application' and composite is not None:
        errors.append('method_application must not set composite')
    if route in {'source_lookup', 'mixed'} and 'retrieval' not in out['components']:
        out['components'].append('retrieval')
        corrections.append('added retrieval component')
    if route == 'direct':
        out['components'] = []
    return out, corrections, errors


def _contrast_neighbors(slug: str, schema: dict) -> list[str]:
    text = schema['profiles'][slug].get('contrast', '')
    found = []
    for other in schema['catalog']['skills']:
        other_slug = other['slug']
        if other_slug != slug and re.search(rf'(?<![A-Za-z0-9_-]){re.escape(other_slug)}(?![A-Za-z0-9_-])', text):
            found.append(other_slug)
    return found


def expand_candidates(coarse: dict, schema: dict, max_candidates: int = 10) -> list[str]:
    ranked: list[str] = []

    def add(slug: str) -> None:
        if slug in schema['slugs'] and slug not in ranked:
            ranked.append(slug)

    for slug in coarse.get('candidate_skills', []):
        add(slug)
    for fid in coarse.get('framework_candidates', []):
        for slug in schema['frameworks'][fid]['atomic_skills']:
            add(slug)
    seed = list(ranked)
    for slug in seed:
        for neighbor in _contrast_neighbors(slug, schema):
            add(neighbor)
    for group in coarse.get('candidate_groups', []):
        for slug in schema['groups'].get(group, []):
            add(slug)
    if len(ranked) < 5:
        for slug in seed:
            group = schema['skills'][slug]['group']
            for peer in schema['groups'].get(group, []):
                add(peer)
    return ranked[:max_candidates]


def normalize_final(pred: dict, schema: dict, allowed_candidates: set[str] | None = None) -> tuple[dict, list[str], list[str]]:
    corrections: list[str] = []
    errors: list[str] = []
    route = pred.get('route')
    if route not in ROUTES:
        errors.append(f'invalid route {route}')
    atoms = _normalize_string_list(pred.get('atomic_skills', []), schema['slugs'], 'atomic_skill', 4, corrections, errors)
    if allowed_candidates is not None:
        outside = [x for x in atoms if x not in allowed_candidates]
        if outside:
            errors.append('atomic skill outside candidate pool: ' + ','.join(outside))
    framework = pred.get('framework')
    if framework is not None and framework not in schema['framework_ids']:
        fixed = _near_value(framework, schema['framework_ids'])
        if fixed:
            corrections.append(f'framework:{framework}->{fixed}')
            framework = fixed
        else:
            errors.append(f'unknown framework {framework}')
    composite = pred.get('composite')
    if composite is not None and composite not in schema['composites']:
        fixed = _near_value(composite, schema['composites'])
        if fixed:
            corrections.append(f'composite:{composite}->{fixed}')
            composite = fixed
        else:
            errors.append(f'unknown composite {composite}')
    components = pred.get('components') if isinstance(pred.get('components'), list) else []
    components = list(dict.fromkeys(x for x in components if isinstance(x, str)))
    out = {
        'route': route,
        'framework': framework,
        'atomic_skills': atoms,
        'composite': composite,
        'components': components,
    }
    if route in {'direct', 'source_lookup'} and atoms:
        errors.append(f'{route} must not select atomic skills')
    if route == 'composite_task' and not composite:
        errors.append('composite_task requires composite')
    if route == 'method_application' and composite is not None:
        errors.append('method_application must not set composite')
    if route in {'source_lookup', 'mixed'} and 'retrieval' not in out['components']:
        out['components'].append('retrieval')
        corrections.append('added retrieval component')
    if route == 'direct':
        out['components'] = []
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


def _call_and_normalize(case_prompt: str, args, system: str, normalizer, payloads: list[dict]) -> tuple[dict, list[str], list[str], bool, dict]:
    repair_attempted = False
    content, payload = post_chat(args.base_url, args.api_key, args.model, system, case_prompt, args.timeout, not args.no_response_format)
    payloads.append(payload)
    try:
        raw = parse_json_object(content)
    except ValueError as parse_error:
        repair_attempted = True
        repair = _repair_prompt(case_prompt, str(parse_error), content)
        content2, payload2 = post_chat(args.base_url, args.api_key, args.model, system, repair, args.timeout, not args.no_response_format)
        payloads.append(payload2)
        raw = parse_json_object(content2)
    pred, corrections, errors = normalizer(raw)
    initial_errors = list(errors)
    if errors:
        repair_attempted = True
        repair = _repair_prompt(case_prompt, json.dumps(errors, ensure_ascii=False), json.dumps(raw, ensure_ascii=False))
        content2, payload2 = post_chat(args.base_url, args.api_key, args.model, system, repair, args.timeout, not args.no_response_format)
        payloads.append(payload2)
        raw2 = parse_json_object(content2)
        pred2, corr2, errors2 = normalizer(raw2)
        raw, pred, corrections, errors = raw2, pred2, corrections + corr2, errors2
    return pred, corrections, errors, repair_attempted, {'raw': raw, 'initial_errors': initial_errors}


def _final_from_coarse(coarse: dict) -> dict:
    return {
        'route': coarse['route'],
        'framework': None,
        'atomic_skills': [],
        'composite': None,
        'components': list(coarse.get('components') or []),
    }


def run_one(case: dict, args, coarse_system: str, schema: dict) -> dict:
    started = time.perf_counter()
    payloads: list[dict] = []
    corrections: list[str] = []
    repair_count = 0
    result = {
        'id': case['id'],
        'benchmark_level': case['benchmark_level'],
        'type': case.get('type'),
        'prompt': case['prompt'],
        'architecture': 'two-stage-v5',
    }
    try:
        coarse, corr1, err1, repaired1, meta1 = _call_and_normalize(
            case['prompt'], args, coarse_system,
            lambda raw: normalize_stage1(raw, schema),
            payloads,
        )
        corrections.extend('stage1:' + x for x in corr1)
        repair_count += int(repaired1)
        result['coarse_prediction'] = coarse
        result['coarse_raw_prediction'] = meta1['raw']
        result['coarse_initial_validation_errors'] = meta1['initial_errors']
        if err1:
            pred = _final_from_coarse(coarse)
            final_errors = ['stage1: ' + x for x in err1]
            result['candidate_pool'] = []
            result['stage2_used'] = False
        elif coarse['route'] in {'direct', 'source_lookup'}:
            pred = _final_from_coarse(coarse)
            pred, corr_final, final_errors = normalize_final(pred, schema)
            corrections.extend('final:' + x for x in corr_final)
            result['candidate_pool'] = []
            result['stage2_used'] = False
        else:
            candidates = expand_candidates(coarse, schema)
            if not candidates:
                pred = _final_from_coarse(coarse)
                final_errors = ['stage2 candidate pool is empty']
                result['candidate_pool'] = []
                result['stage2_used'] = False
            else:
                result['candidate_pool'] = candidates
                result['stage2_used'] = True
                fine_system = build_stage2_prompt(schema, coarse, candidates)
                fine, corr2, err2, repaired2, meta2 = _call_and_normalize(
                    case['prompt'], args, fine_system,
                    lambda raw: normalize_final(raw, schema, set(candidates)),
                    payloads,
                )
                corrections.extend('stage2:' + x for x in corr2)
                repair_count += int(repaired2)
                pred = fine
                final_errors = err2
                result['fine_raw_prediction'] = meta2['raw']
                result['fine_initial_validation_errors'] = meta2['initial_errors']
                result['fine_prompt_chars'] = len(fine_system)
        passed, reasons = score_case(case, pred, final_errors)
        result.update({
            'prediction': pred,
            'passed': passed,
            'reasons': reasons,
            'validation_errors': final_errors,
            'corrections': corrections,
            'repair_attempted': repair_count > 0,
            'repair_count': repair_count,
            'stage_calls': len(payloads),
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
            'repair_attempted': repair_count > 0,
            'repair_count': repair_count,
            'stage_calls': len(payloads),
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
    pools = [len(r.get('candidate_pool') or []) for r in results if r.get('stage2_used')]
    stage_calls = [r.get('stage_calls', 0) for r in results]
    return {
        'architecture': 'two-stage-v5',
        'cases_total': len(results),
        'scored': len(scored),
        'passed': passed,
        'pass_rate': round(passed / len(scored), 4) if scored else None,
        'by_level': by_level,
        'by_type': by_type,
        'errors': sum(bool(r.get('error')) for r in results),
        'repairs': sum(r.get('repair_count', 0) for r in results),
        'normalizations': sum(bool(r.get('corrections')) for r in results),
        'stage2_calls': sum(bool(r.get('stage2_used')) for r in results),
        'avg_candidate_pool': round(sum(pools) / len(pools), 2) if pools else 0,
        'avg_stage_calls': round(sum(stage_calls) / len(stage_calls), 2) if stage_calls else 0,
        'avg_latency_s': round(sum(lats) / len(lats), 3) if lats else None,
        'total_tokens': int(sum(toks)) if toks else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description='Run two-stage routing benchmark against an OpenAI-compatible endpoint.')
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
    coarse_system = build_stage1_prompt(schema)
    if args.dry_run:
        counts = {}
        for c in cases:
            counts[c['type']] = counts.get(c['type'], 0) + 1
        sample_coarse = {
            'route': 'method_application',
            'candidate_groups': ['organization'],
            'candidate_skills': schema['groups']['organization'][:4],
            'framework_candidates': [],
            'composite': None,
            'components': [],
        }
        sample_pool = expand_candidates(sample_coarse, schema)
        fine_sample = build_stage2_prompt(schema, sample_coarse, sample_pool)
        print(json.dumps({
            'ok': True,
            'architecture': 'two-stage-v5',
            'cases': len(cases),
            'coarse_prompt_chars': len(coarse_system),
            'sample_fine_prompt_chars': len(fine_sample),
            'sample_candidate_pool': len(sample_pool),
            'routing_profiles': len(schema['profiles']),
            'atomic_cases': sum(c['benchmark_level'] == 'atomic' for c in cases),
            'system_router_cases': sum(c['benchmark_level'] == 'system_router' for c in cases),
            'by_type': counts,
        }, ensure_ascii=False, indent=2))
        return
    if not args.base_url or not args.model:
        ap.error('set --base-url and --model')
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        results = list(ex.map(lambda c: run_one(c, args, coarse_system, schema), cases))
    summary = summarize(results)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%Y%m%d-%H%M%S')
    out = Path(args.output) if args.output else RESULTS_DIR / f'router-{args.model.replace("/", "_")}-{stamp}.jsonl'
    with out.open('w', encoding='utf-8') as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    summary_path = out.with_suffix('.summary.json')
    summary_path.write_text(
        json.dumps({'model': args.model, 'base_url': args.base_url, 'summary': summary}, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(out)
    print(summary_path)


if __name__ == '__main__':
    main()
