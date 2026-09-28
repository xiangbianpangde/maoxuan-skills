#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from retrieval.common import iter_corpus

def main():
    cards=json.loads((ROOT/'skills/runtime/RUNTIME_CARDS.json').read_text(encoding='utf-8'))
    catalog=json.loads((ROOT/'skills/atomic/CATALOG.json').read_text(encoding='utf-8'))
    comps=json.loads((ROOT/'skills/runtime/COMPOSITE_CARDS.json').read_text(encoding='utf-8'))
    slugs=[x['slug'] for x in cards['cards']]
    expected=[x['slug'] for x in catalog['skills']]
    assert len(slugs)==25 and len(set(slugs))==25, 'Runtime Cards must contain 25 unique slugs'
    assert set(slugs)==set(expected), f'Runtime card/catalog mismatch: {set(expected)^set(slugs)}'
    banned=('毛泽东','毛选','敌人','战争','武装','阶级斗争','选举','投票','暴力行动')
    for c in cards['cards']:
        assert c.get('objective') and c.get('runtime_name')
        assert 1 <= len(c.get('trigger') or []) <= 4
        assert 3 <= len(c.get('steps') or []) <= 5
        assert 2 <= len(c.get('checks') or []) <= 4
        assert 1 <= len(c.get('avoid') or []) <= 4
        body=json.dumps({k:v for k,v in c.items() if k!='slug'},ensure_ascii=False)
        hits=[x for x in banned if x in body]
        assert not hits, f"{c['slug']} contains banned historical/political runtime terms: {hits}"
        assert len(body) <= 1800, f"{c['slug']} runtime card too large: {len(body)} chars"
    comp_ids={x['id'] for x in comps['cards']}
    assert comp_ids=={'research-and-decision','complex-problem-solving','strategy-analysis','organization-improvement'}
    tasks=[json.loads(x) for x in (ROOT/'eval/task_gain_v2/tasks-v2.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
    assert len(tasks)==40 and len({x['id'] for x in tasks})==40
    assert sum(x['category']=='source-evidence' for x in tasks)==8
    titles={r['title'] for r in iter_corpus(ROOT/'毛选md')}
    missing=[]
    for t in tasks:
        if not t.get('needs_retrieval'): continue
        wanted=t.get('source_title') or ''
        if not any(wanted in title or title in wanted for title in titles):
            missing.append(wanted)
    assert not missing, f'Task source titles not found in corpus: {missing}'
    print(json.dumps({'ok':True,'runtime_cards':len(slugs),'composites':len(comp_ids),'tasks':len(tasks),'source_tasks':8},ensure_ascii=False))

if __name__=='__main__':
    main()
