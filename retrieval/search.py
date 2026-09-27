#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, sqlite3, re
from pathlib import Path
from common import load_config, ROOT
from providers import embeddings as remote_embeddings, rerank

def cosine(a,b):
    s=sum(x*y for x,y in zip(a,b)); na=math.sqrt(sum(x*x for x in a)); nb=math.sqrt(sum(x*x for x in b))
    return s/(na*nb) if na and nb else 0.0

def ensure_db(cfg):
    p=Path(cfg['database'])
    if not p.exists(): raise SystemExit('index missing; run: python3 retrieval/build_index.py')
    return sqlite3.connect(p)

def keyword(con,q,limit):
    q=q.strip(); out=[]
    # exact substring has priority and works well for Chinese.
    for r in con.execute('SELECT source_id,volume,title,path,para_no,text FROM chunks WHERE text LIKE ? OR title LIKE ? LIMIT ?',('%'+q+'%','%'+q+'%',limit)):
        out.append((*r,2.0))
    if len(out)>=limit: return out[:limit]
    try:
        safe=' '.join(re.findall(r'[\w\u4e00-\u9fff]+',q))
        for r in con.execute('SELECT c.source_id,c.volume,c.title,c.path,c.para_no,c.text,bm25(chunk_fts) FROM chunk_fts JOIN chunks c USING(source_id) WHERE chunk_fts MATCH ? ORDER BY bm25(chunk_fts) LIMIT ?',(safe,limit)):
            if r[0] not in {x[0] for x in out}:
                out.append((*r[:6],1/(1+max(0,r[6]))))
    except sqlite3.OperationalError:
        pass
    return out[:limit]

def hybrid(con,q,cfg,limit):
    lex=keyword(con,q,max(limit*4,30)); scores={r[0]:[r, float(r[6])] for r in lex}
    ecfg=cfg['embedding']
    if ecfg.get('enabled'):
        try:
            qv=remote_embeddings([q],ecfg)[0]
            for sid,vj in con.execute('SELECT source_id,vector_json FROM embeddings'):
                import json as _j
                cs=cosine(qv,_j.loads(vj))
                if sid in scores: scores[sid][1]+=cs
                elif cs>0:
                    r=con.execute('SELECT source_id,volume,title,path,para_no,text FROM chunks WHERE source_id=?',(sid,)).fetchone()
                    scores[sid]=[(*r,0.0),cs]
        except Exception as e:
            print(json.dumps({'warning':'embedding search unavailable','detail':str(e)},ensure_ascii=False))
    ranked=sorted(scores.values(),key=lambda x:x[1],reverse=True)[:max(limit*3,20)]
    rcfg=cfg['rerank']
    if rcfg.get('enabled') and ranked:
        try:
            rr=rerank(q,[x[0][5] for x in ranked],rcfg)
            if rr:
                ordered=[]
                for z in rr:
                    idx=z.get('index')
                    if idx is not None and 0<=idx<len(ranked): ordered.append(ranked[idx])
                ranked=ordered + [x for x in ranked if x not in ordered]
        except Exception as e:
            print(json.dumps({'warning':'rerank unavailable','detail':str(e)},ensure_ascii=False))
    return [(*x[0][:6],x[1]) for x in ranked[:limit]]

def emit(rows):
    print(json.dumps([{'source_id':r[0],'volume':r[1],'title':r[2],'path':r[3],'paragraph':r[4],'text':r[5],'score':round(float(r[6]),6)} for r in rows],ensure_ascii=False,indent=2))

def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('search'); s.add_argument('query'); s.add_argument('--limit',type=int,default=8)
    h=sub.add_parser('hybrid'); h.add_argument('query'); h.add_argument('--limit',type=int,default=8)
    c=sub.add_parser('catalog'); c.add_argument('--volume')
    sh=sub.add_parser('show'); sh.add_argument('title')
    a=ap.parse_args(); cfg=load_config(); con=ensure_db(cfg)
    if a.cmd=='search': emit(keyword(con,a.query,a.limit)); return
    if a.cmd=='hybrid': emit(hybrid(con,a.query,cfg,a.limit)); return
    if a.cmd=='catalog':
        sql='SELECT DISTINCT volume,article_no,title,path FROM chunks'; params=[]
        if a.volume:
            vol={'第一卷':1,'第二卷':2,'第三卷':3,'第四卷':4,'第五卷':5}.get(a.volume)
            if vol: sql+=' WHERE volume=?'; params=[vol]
        sql+=' ORDER BY volume,article_no'
        print(json.dumps([{'volume':r[0],'article_no':r[1],'title':r[2],'path':r[3]} for r in con.execute(sql,params)],ensure_ascii=False,indent=2)); return
    if a.cmd=='show':
        rows=con.execute('SELECT source_id,path,para_no,text FROM chunks WHERE title LIKE ? ORDER BY volume,article_no,para_no',('%'+a.title+'%',)).fetchall()
        print(json.dumps([{'source_id':r[0],'path':r[1],'paragraph':r[2],'text':r[3]} for r in rows],ensure_ascii=False,indent=2))

if __name__=='__main__': main()
