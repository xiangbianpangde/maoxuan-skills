#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import difflib, json, re, unicodedata

ROOT=Path(__file__).resolve().parents[1]
CAT=json.loads((ROOT/'skills/atomic/CATALOG.json').read_text(encoding='utf-8'))


def norm(s: str) -> str:
    s=re.sub(r'\[\s*\d+\s*\]', '', s)
    s=unicodedata.normalize('NFKC',s)
    return ''.join(ch for ch in s if not ch.isspace() and unicodedata.category(ch)[0] not in 'PS')


def corpus():
    out=[]
    for p in sorted((ROOT/'毛选md').glob('第*卷/*.md')):
        text=p.read_text(encoding='utf-8',errors='replace')
        pars=[x.strip() for x in re.split(r'\n\s*\n',text) if x.strip()]
        m=re.match(r'(\d+)[-_]?(.*)',p.stem)
        ano=int(m.group(1)) if m else 0
        title=(m.group(2) if m else p.stem).strip(' -_')
        v={'第一卷':1,'第二卷':2,'第三卷':3,'第四卷':4,'第五卷':5}.get(p.parent.name,0)
        out.append({'path':p,'rel':p.relative_to(ROOT).as_posix(),'volume':v,'article_no':ano,'title':title,'pars':pars,'normpars':[norm(x) for x in pars]})
    return out


def sid(a,i):
    return f"MX-V{a['volume']:02d}-A{a['article_no']:03d}-P{i+1:04d}"


def r_section(text: str) -> str:
    m=re.search(r'##\s*R\s*[—-].*?(.*?)(?=\n##\s|\Z)',text,re.S)
    return m.group(1) if m else ''


def source_titles(text: str):
    titles=[]
    m=re.search(r'^source_chapter:\s*(.+)$',text,re.M)
    if m:
        for x in re.split(r'[;；]',m.group(1)):
            x=re.sub(r'[（(]\d{4}[^）)]*[）)]','',x).strip()
            if x: titles.append(x)
    for x in re.findall(r'—\s*《([^》]+)》', r_section(text)):
        x=x.strip()
        if x: titles.append(x)
    return list(dict.fromkeys(titles))


def reading_quotes(text: str):
    sec=r_section(text)
    out=[]; pending=[]

    def flush(source=None):
        nonlocal pending
        q=' '.join(x.strip() for x in pending if x.strip()).strip()
        if len(norm(q))>=12:
            out.append({'quote':q,'declared_source':source})
        pending=[]

    for raw in sec.splitlines():
        stripped=raw.lstrip()
        if not stripped.startswith('>'):
            if pending: flush(None)
            continue
        z=stripped[1:].strip()
        # Upstream commonly inserts an empty blockquote line between quote and attribution.
        # Do not flush here; preserve the quote until the following —《source》 line.
        if not z:
            continue
        am=re.match(r'—\s*《([^》]+)》', z)
        if am:
            flush(am.group(1).strip())
            continue
        if z.startswith('—'):
            flush(None)
            continue
        pending.append(z)
    if pending: flush(None)
    return out


def title_matches(title: str, arts):
    nt=norm(title)
    exact=[a for a in arts if nt and (nt in norm(a['title']) or norm(a['title']) in nt)]
    if exact:
        return exact
    scored=[]
    for a in arts:
        at=norm(a['title'])
        if not at: continue
        score=difflib.SequenceMatcher(None,nt,at,autojunk=False).ratio()
        if score>=0.72:
            scored.append((score,a))
    scored.sort(key=lambda x:x[0], reverse=True)
    return [a for _,a in scored[:3]]


def paragraph_windows(a, max_span=3):
    n=len(a['normpars'])
    for i in range(n):
        combined=''
        for span in range(1,max_span+1):
            j=i+span-1
            if j>=n: break
            combined += a['normpars'][j]
            yield i,j,combined


def paragraph_for_offset(a, pos: int) -> int:
    cur=0
    for i,p in enumerate(a['normpars']):
        nxt=cur+len(p)
        if pos < nxt:
            return i
        cur=nxt
    return max(0,len(a['normpars'])-1)


def ellipsis_segments(raw: str):
    parts=re.split(r'(?:…{2,}|\.\.\.+|⋯+)', raw)
    return [norm(x) for x in parts if len(norm(x))>=8]


def ordered_ellipsis_match(raw: str, a):
    segs=ellipsis_segments(raw)
    if len(segs)<2:
        return None
    full=''.join(a['normpars'])
    cursor=0; first=None; last=None
    for seg in segs:
        idx=full.find(seg,cursor)
        if idx<0:
            return None
        if first is None: first=idx
        last=idx+len(seg)-1
        cursor=idx+len(seg)
    i=paragraph_for_offset(a,first or 0)
    j=paragraph_for_offset(a,last or 0)
    return i,j


def fuzzy_score(q: str, w: str) -> float:
    if not q or not w: return 0.0
    sm=difflib.SequenceMatcher(None,q,w,autojunk=False)
    blocks=sm.get_matching_blocks()
    coverage=sum(b.size for b in blocks)/len(q)
    longest=max((b.size for b in blocks),default=0)/len(q)
    anchors=[]
    if len(q)>=36:
        width=min(18,max(12,len(q)//6))
        for frac in (0.15,0.45,0.75):
            start=min(max(0,int(len(q)*frac)), max(0,len(q)-width))
            anchors.append(q[start:start+width])
    anchor_rate=(sum(a in w for a in anchors)/len(anchors)) if anchors else 0.0
    return max(longest, coverage*0.97, anchor_rate*0.94)


def make_match(a,i,j,kind,score,q):
    ids=[sid(a,k) for k in range(i,j+1)]
    return {'source_id':ids[0],'source_ids':ids,'path':a['rel'],'match_type':kind,'score':round(score,4),'quote_preview':q[:120]}


def find_quote(q: str, pool):
    nq=norm(q)
    if len(nq)<12: return []
    for a in pool:
        for i,j,nw in paragraph_windows(a):
            if nq in nw or (len(nw)>=18 and nw in nq):
                return [make_match(a,i,j,'exact',1.0,q)]
    # Ellipsized quotations intentionally omit material. Require all substantial
    # segments to appear in order in the same declared source article.
    for a in pool:
        span=ordered_ellipsis_match(q,a)
        if span:
            i,j=span
            return [make_match(a,i,j,'ellipsis',1.0,q)]
    best=None
    for a in pool:
        for i,j,nw in paragraph_windows(a):
            score=fuzzy_score(nq,nw)
            if best is None or score>best[0]:
                best=(score,a,i,j)
    # Keep fuzzy alignment conservative; lower scores are more useful as unresolved
    # audit cases than as false evidence links.
    if best and best[0]>=0.90:
        score,a,i,j=best
        return [make_match(a,i,j,'fuzzy',score,q)]
    return []


arts=corpus(); result={}
for s in CAT['skills']:
    p=ROOT/s['vendor_path']
    rec={'source_chapter_matches':[],'reading_quote_matches':[],'status':'vendor-missing' if not p.exists() else 'ok'}
    if p.exists():
        text=p.read_text(encoding='utf-8',errors='replace')
        titles=source_titles(text)
        title_map={}
        for title in titles:
            matches=title_matches(title,arts)
            title_map[title]=matches
            rec['source_chapter_matches'].append({
                'declared':title,
                'local_source_status':'matched' if matches else 'not_found',
                'matches':[a['rel'] for a in matches]
            })
        all_candidates=[]
        for xs in title_map.values():
            for a in xs:
                if a not in all_candidates: all_candidates.append(a)
        for item in reading_quotes(text):
            q=item['quote']; declared=item['declared_source']
            if declared:
                pool=title_map.get(declared)
                if pool is None:
                    pool=title_matches(declared,arts)
                source_status='matched' if pool else 'not_found'
            else:
                pool=all_candidates or arts
                source_status='unspecified'
            found=find_quote(q,pool) if pool else []
            rec['reading_quote_matches'].append({
                'declared_source':declared,
                'local_source_status':source_status,
                'match_status': found[0]['match_type'] if found else ('source_not_found' if source_status=='not_found' else 'unresolved'),
                'quote_preview':q[:160],
                'matches':found
            })
    result[s['slug']]=rec

out=ROOT/'evidence/skill-source-map.generated.json'
out.write_text(json.dumps({'schema_version':'2.1','skills':result},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(out)
