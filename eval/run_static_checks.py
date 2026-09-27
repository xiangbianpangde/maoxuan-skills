#!/usr/bin/env python3
from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[1]
errs=[]; warns=[]
def req(p):
    if not (ROOT/p).exists(): errs.append(f'missing: {p}')
for p in ['SKILL.md','skills/atomic/CATALOG.json','skills/frameworks/FRAMEWORKS.json','upstream/UPSTREAM_LOCK.json','retrieval/build_index.py','retrieval/search.py','router/ROUTING.md']:
    req(p)
cat=json.loads((ROOT/'skills/atomic/CATALOG.json').read_text(encoding='utf-8'))
if len(cat['skills'])!=25: errs.append(f"atomic skill count={len(cat['skills'])}, expected 25")
slugs={x['slug'] for x in cat['skills']}
fw=json.loads((ROOT/'skills/frameworks/FRAMEWORKS.json').read_text(encoding='utf-8'))
if len(fw['frameworks'])!=7: errs.append(f"framework count={len(fw['frameworks'])}, expected 7")
for f in fw['frameworks']:
    for s in f['atomic_skills']:
        if s not in slugs: errs.append(f"framework {f['id']} references unknown skill {s}")
for p in (ROOT/'skills/composite').glob('*/SKILL.md'):
    text=p.read_text(encoding='utf-8')
    if 'Evidence rule' not in text: errs.append(f'{p.relative_to(ROOT)} missing Evidence rule')
if not (ROOT/'毛选md').exists(): warns.append('local overlay does not contain 毛选md; expected when applied to target repository')
missing_vendor=[s for s in cat['skills'] if not (ROOT/s['vendor_path']).exists()]
if missing_vendor: warns.append(f'vendor not synced: {len(missing_vendor)} atomic skills; run scripts/sync_upstreams.py')
print(json.dumps({'ok':not errs,'errors':errs,'warnings':warns,'atomic_skills':len(cat['skills']),'frameworks':len(fw['frameworks'])},ensure_ascii=False,indent=2))
sys.exit(1 if errs else 0)
