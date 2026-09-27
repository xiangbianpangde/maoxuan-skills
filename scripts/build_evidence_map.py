#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json,re,unicodedata
ROOT=Path(__file__).resolve().parents[1]
CAT=json.loads((ROOT/'skills/atomic/CATALOG.json').read_text(encoding='utf-8'))

def norm(s):
    s=unicodedata.normalize('NFKC',s)
    return ''.join(ch for ch in s if not ch.isspace() and unicodedata.category(ch)[0] not in 'PS')

def corpus():
    out=[]
    for p in sorted((ROOT/'毛选md').glob('第*卷/*.md')):
        text=p.read_text(encoding='utf-8',errors='replace')
        pars=[x.strip() for x in re.split(r'\n\s*\n',text) if x.strip()]
        m=re.match(r'(\d+)[-_]?(.*)',p.stem); ano=int(m.group(1)) if m else 0; title=(m.group(2) if m else p.stem).strip(' -_')
        v={'第一卷':1,'第二卷':2,'第三卷':3,'第四卷':4,'第五卷':5}.get(p.parent.name,0)
        out.append({'path':p,'rel':p.relative_to(ROOT).as_posix(),'volume':v,'article_no':ano,'title':title,'pars':pars,'normpars':[norm(x) for x in pars]})
    return out

def sid(a,i): return f"MX-V{a['volume']:02d}-A{a['article_no']:03d}-P{i+1:04d}"

def source_chapters(text):
    m=re.search(r'^source_chapter:\s*(.+)$',text,re.M)
    if not m:return []
    return [re.sub(r'[（(]\d{4}[^）)]*[）)]','',x).strip() for x in re.split(r'[;；]',m.group(1)) if x.strip()]

def reading_quotes(text):
    m=re.search(r'##\s*R\s*[—-].*?(.*?)(?=\n##\s|\Z)',text,re.S)
    if not m:return []
    q=[]
    for line in m.group(1).splitlines():
        if line.lstrip().startswith('>'):
            z=line.lstrip()[1:].strip()
            if len(norm(z))>=12 and not z.startswith('—'): q.append(z)
    return q

arts=corpus(); result={}
for s in CAT['skills']:
    p=ROOT/s['vendor_path']; rec={'source_chapter_matches':[],'reading_quote_matches':[],'status':'vendor-missing' if not p.exists() else 'ok'}
    if p.exists():
        text=p.read_text(encoding='utf-8',errors='replace')
        candidates=[]
        for ch in source_chapters(text):
            nch=norm(ch)
            matches=[a for a in arts if nch and (nch in norm(a['title']) or norm(a['title']) in nch)]
            rec['source_chapter_matches'].append({'declared':ch,'matches':[a['rel'] for a in matches]})
            candidates.extend(matches)
        pool=candidates or arts
        for q in reading_quotes(text):
            nq=norm(q); found=[]
            for a in pool:
                for i,np in enumerate(a['normpars']):
                    if len(nq)>=12 and (nq in np or (len(np)>=18 and np in nq)):
                        found.append({'source_id':sid(a,i),'path':a['rel'],'quote_preview':q[:120]}); break
                if found: break
            rec['reading_quote_matches'].append({'quote_preview':q[:160],'matches':found})
    result[s['slug']]=rec
out=ROOT/'evidence/skill-source-map.generated.json'; out.write_text(json.dumps({'schema_version':'1.0','skills':result},ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(out)
