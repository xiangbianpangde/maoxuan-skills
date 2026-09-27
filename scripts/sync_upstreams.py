#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json, urllib.request, hashlib

ROOT=Path(__file__).resolve().parents[1]
LOCK=json.loads((ROOT/'upstream/UPSTREAM_LOCK.json').read_text(encoding='utf-8'))
CAT=json.loads((ROOT/'skills/atomic/CATALOG.json').read_text(encoding='utf-8'))

def dl(url,dst):
    dst.parent.mkdir(parents=True,exist_ok=True)
    req=urllib.request.Request(url,headers={'User-Agent':'maoxuan-skills-sync/1.0'})
    with urllib.request.urlopen(req,timeout=60) as r: data=r.read()
    dst.write_bytes(data)
    return hashlib.sha256(data).hexdigest()

def main():
    report=[]
    k=next(x for x in LOCK['sources'] if x['id']=='atomic')
    base=f"https://raw.githubusercontent.com/{k['repo']}/{k['commit']}"
    for s in CAT['skills']:
        for fn in ('SKILL.md','test-prompts.json'):
            url=f"{base}/{s['slug']}/{fn}"; dst=ROOT/'vendor/kangarooking'/s['slug']/fn
            report.append({'url':url,'path':dst.relative_to(ROOT).as_posix(),'sha256':dl(url,dst)})
    l=next(x for x in LOCK['sources'] if x['id']=='framework')
    base=f"https://raw.githubusercontent.com/{l['repo']}/{l['commit']}"
    paths=['SKILL.md','README.md','LICENSE']+[f'references/research/0{i}-{name}.md' for i,name in [
        (1,'core-writings'),(2,'strategic-thinking'),(3,'expression-dna'),(4,'external-views'),(5,'decisions'),(6,'timeline')]]
    for p in paths:
        dst=ROOT/'vendor/leezythu'/p
        report.append({'url':f'{base}/{p}','path':dst.relative_to(ROOT).as_posix(),'sha256':dl(f'{base}/{p}',dst)})
    (ROOT/'vendor/SYNC_MANIFEST.json').write_text(json.dumps({'files':report},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'synced {len(report)} files')

if __name__=='__main__': main()
