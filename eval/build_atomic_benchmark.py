#!/usr/bin/env python3
from __future__ import annotations
from collections import Counter
from pathlib import Path
import json, sys

ROOT=Path(__file__).resolve().parents[1]
CAT=json.loads((ROOT/'skills/atomic/CATALOG.json').read_text(encoding='utf-8'))
OUT_INV=ROOT/'eval/atomic-test-inventory.generated.json'
OUT_BENCH=ROOT/'eval/atomic-routing-benchmark.generated.jsonl'

errors=[]; rows=[]; bench=[]
for skill in CAT['skills']:
    slug=skill['slug']
    skill_path=ROOT/skill['vendor_path']
    test_path=skill_path.parent/'test-prompts.json'
    if not skill_path.exists():
        errors.append(f'{slug}: missing SKILL.md at {skill_path.relative_to(ROOT)}')
        continue
    if not test_path.exists():
        errors.append(f'{slug}: missing test-prompts.json')
        continue
    try:
        data=json.loads(test_path.read_text(encoding='utf-8'))
    except Exception as e:
        errors.append(f'{slug}: invalid test JSON: {e}')
        continue
    if data.get('skill') and data.get('skill') != slug:
        errors.append(f"{slug}: test file declares skill={data.get('skill')}")
    cases=data.get('test_cases')
    if not isinstance(cases,list) or not cases:
        errors.append(f'{slug}: no test_cases')
        continue
    ids=[str(x.get('id','')).strip() for x in cases]
    if any(not x for x in ids): errors.append(f'{slug}: empty test case id')
    if len(set(ids))!=len(ids): errors.append(f'{slug}: duplicate test case id')
    types=Counter(str(x.get('type','')).strip() for x in cases)
    if types['should_trigger']<1: errors.append(f'{slug}: no should_trigger case')
    if types['should_not_trigger']<1: errors.append(f'{slug}: no should_not_trigger case')
    min_pass=data.get('minimum_pass_rate')
    if min_pass is not None and not (isinstance(min_pass,(int,float)) and 0 < min_pass <= 1):
        errors.append(f'{slug}: invalid minimum_pass_rate={min_pass!r}')
    for c in cases:
        prompt=str(c.get('prompt','')).strip()
        expected=str(c.get('expected_behavior','')).strip()
        ctype=str(c.get('type','')).strip()
        if not prompt: errors.append(f"{slug}:{c.get('id')}: empty prompt")
        if not expected: errors.append(f"{slug}:{c.get('id')}: empty expected_behavior")
        bench.append({
            'id':f"{slug}:{c.get('id')}",
            'source':'kangarooking/mao-selected-works-skill',
            'target_skill':slug,
            'type':ctype,
            'prompt':prompt,
            'expected_behavior':expected,
            'notes':c.get('notes'),
            'expected_route':'method_application' if ctype=='should_trigger' else None,
            'expected_should_trigger': True if ctype=='should_trigger' else (False if ctype=='should_not_trigger' else None)
        })
    rows.append({
        'skill':slug,
        'test_path':test_path.relative_to(ROOT).as_posix(),
        'case_count':len(cases),
        'type_counts':dict(sorted(types.items())),
        'minimum_pass_rate':min_pass
    })

summary={
    'skills_expected':len(CAT['skills']),
    'skills_with_valid_test_files':len(rows),
    'cases_total':len(bench),
    'should_trigger':sum(x['type']=='should_trigger' for x in bench),
    'should_not_trigger':sum(x['type']=='should_not_trigger' for x in bench),
    'edge_case':sum(x['type']=='edge_case' for x in bench),
    'errors':errors
}
OUT_INV.write_text(json.dumps({'schema_version':'1.0','summary':summary,'skills':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with OUT_BENCH.open('w',encoding='utf-8') as f:
    for item in bench:
        f.write(json.dumps(item,ensure_ascii=False)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
print(OUT_INV); print(OUT_BENCH)
if errors: sys.exit(1)
