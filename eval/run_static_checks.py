#!/usr/bin/env python3
from pathlib import Path
import json, sys

ROOT=Path(__file__).resolve().parents[1]
errs=[]; warns=[]

def req(p):
    if not (ROOT/p).exists(): errs.append(f'missing: {p}')

for p in ['SKILL.md','.gitmodules','skills/atomic/CATALOG.json','skills/frameworks/FRAMEWORKS.json','upstream/UPSTREAM_LOCK.json','retrieval/build_index.py','retrieval/search.py','router/ROUTING.md','evidence/external-source-allowlist.json']:
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

# Evidence-quality gate. Generated files are produced earlier in CI; for a
# lightweight local static check they remain optional and produce a warning.
allow_path=ROOT/'evidence/external-source-allowlist.json'
allow=json.loads(allow_path.read_text(encoding='utf-8')) if allow_path.exists() else {'sources':[]}
allowed=set()
for item in allow.get('sources',[]):
    allowed.add(item['canonical'])
    allowed.update(item.get('aliases',[]))

emap_path=ROOT/'evidence/skill-source-map.generated.json'
coverage_path=ROOT/'eval/evidence-coverage.generated.json'
if emap_path.exists() and coverage_path.exists():
    emap=json.loads(emap_path.read_text(encoding='utf-8'))
    coverage=json.loads(coverage_path.read_text(encoding='utf-8'))
    summary=coverage.get('summary',{})
    if summary.get('quotes_unresolved_with_local_source',0)!=0:
        errs.append(f"unresolved local-source quotes={summary.get('quotes_unresolved_with_local_source')}")
    if summary.get('local_quote_match_rate') != 1.0:
        errs.append(f"local quote match rate={summary.get('local_quote_match_rate')}, expected 1.0")

    unexpected_missing=[]
    for slug,rec in emap.get('skills',{}).items():
        for x in rec.get('source_chapter_matches',[]):
            if x.get('local_source_status')=='not_found' and x.get('declared') not in allowed:
                unexpected_missing.append(f"{slug}: chapter {x.get('declared')}")
        for q in rec.get('reading_quote_matches',[]):
            if q.get('match_status')=='source_not_found' and q.get('declared_source') not in allowed:
                unexpected_missing.append(f"{slug}: quote source {q.get('declared_source')}")
            for m in q.get('matches',[]):
                if m.get('match_type')=='fuzzy' and float(m.get('score',0))<0.90:
                    errs.append(f"{slug}: fuzzy evidence score below 0.90 ({m.get('score')})")
                if m.get('match_type')=='composite' and m.get('span_mode')!='noncontiguous':
                    errs.append(f"{slug}: composite evidence missing noncontiguous span marker")
    if unexpected_missing:
        errs.extend('unapproved external source: '+x for x in unexpected_missing)
else:
    warns.append('generated evidence audit not found; run build_evidence_map.py and evidence_coverage.py for full validation')

print(json.dumps({'ok':not errs,'errors':errs,'warnings':warns,'atomic_skills':len(cat['skills']),'frameworks':len(fw['frameworks']),'composites':len(composites)},ensure_ascii=False,indent=2))
sys.exit(1 if errs else 0)
