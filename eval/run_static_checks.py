#!/usr/bin/env python3
from pathlib import Path
import json, sys

ROOT=Path(__file__).resolve().parents[1]
errs=[]; warns=[]

def req(p):
    if not (ROOT/p).exists(): errs.append(f'missing: {p}')

for p in ['SKILL.md','.gitmodules','skills/atomic/CATALOG.json','skills/frameworks/FRAMEWORKS.json','upstream/UPSTREAM_LOCK.json','retrieval/build_index.py','retrieval/search.py','router/ROUTING.md']:
    req(p)

cat=json.loads((ROOT/'skills/atomic/CATALOG.json').read_text(encoding='utf-8'))
if len(cat['skills'])!=25: errs.append(f"atomic skill count={len(cat['skills'])}, expected 25")
slugs={x['slug'] for x in cat['skills']}
if len(slugs)!=len(cat['skills']): errs.append('duplicate atomic skill slug')

fw=json.loads((ROOT/'skills/frameworks/FRAMEWORKS.json').read_text(encoding='utf-8'))
if len(fw['frameworks'])!=7: errs.append(f"framework count={len(fw['frameworks'])}, expected 7")
for f in fw['frameworks']:
    for s in f['atomic_skills']:
        if s not in slugs: errs.append(f"framework {f['id']} references unknown skill {s}")

composites=list((ROOT/'skills/composite').glob('*/SKILL.md'))
if len(composites)!=4: errs.append(f'composite skill count={len(composites)}, expected 4')
for p in composites:
    text=p.read_text(encoding='utf-8')
    if 'Evidence rule' not in text: errs.append(f'{p.relative_to(ROOT)} missing Evidence rule')

if not (ROOT/'毛选md').exists():
    warns.append('corpus missing: 毛选md/')

missing_vendor=[s for s in cat['skills'] if not (ROOT/s['vendor_path']).exists()]
if missing_vendor:
    warns.append(f'atomic submodule not initialized or incomplete: {len(missing_vendor)} skill files missing; run python3 scripts/sync_upstreams.py')

framework_vendor=ROOT/'vendor/leezythu/SKILL.md'
if not framework_vendor.exists():
    warns.append('framework submodule not initialized; run python3 scripts/sync_upstreams.py')

print(json.dumps({'ok':not errs,'errors':errs,'warnings':warns,'atomic_skills':len(cat['skills']),'frameworks':len(fw['frameworks']),'composites':len(composites)},ensure_ascii=False,indent=2))
sys.exit(1 if errs else 0)
