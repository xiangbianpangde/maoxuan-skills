#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sqlite3
from pathlib import Path
from common import load_config, iter_corpus
from providers import embeddings

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--embeddings', action='store_true', help='also build remote embeddings using retrieval/config.json')
    args=ap.parse_args()
    cfg=load_config(); db=Path(cfg['database']); corpus=Path(cfg['corpus'])
    if not corpus.exists(): raise SystemExit(f'corpus not found: {corpus}')
    db.parent.mkdir(parents=True, exist_ok=True)
    con=sqlite3.connect(db)
    con.executescript("""
    DROP TABLE IF EXISTS chunks;
    DROP TABLE IF EXISTS chunk_fts;
    DROP TABLE IF EXISTS embeddings;
    CREATE TABLE chunks(source_id TEXT PRIMARY KEY, volume INTEGER, article_no INTEGER, title TEXT, path TEXT, para_no INTEGER, text TEXT);
    CREATE TABLE embeddings(source_id TEXT PRIMARY KEY, vector_json TEXT NOT NULL);
    """)
    fts=True
    try:
        con.execute("CREATE VIRTUAL TABLE chunk_fts USING fts5(source_id UNINDEXED,title,text, tokenize='unicode61')")
    except sqlite3.OperationalError:
        fts=False
    rows=list(iter_corpus(corpus))
    con.executemany('INSERT INTO chunks VALUES(:source_id,:volume,:article_no,:title,:path,:para_no,:text)',rows)
    if fts:
        con.executemany('INSERT INTO chunk_fts(source_id,title,text) VALUES(:source_id,:title,:text)',rows)
    con.commit()
    if args.embeddings:
        ecfg=cfg['embedding']; bs=int(ecfg.get('batch_size',16))
        if not ecfg.get('enabled'):
            raise SystemExit('embedding.enabled=false in config; enable it first')
        for start in range(0,len(rows),bs):
            batch=rows[start:start+bs]
            vecs=embeddings([x['text'] for x in batch],ecfg)
            con.executemany('INSERT OR REPLACE INTO embeddings(source_id,vector_json) VALUES(?,?)',[(x['source_id'],json.dumps(v,separators=(',',':'))) for x,v in zip(batch,vecs)])
            con.commit(); print(f'embeddings {min(start+bs,len(rows))}/{len(rows)}')
    print(json.dumps({'database':str(db),'chunks':len(rows),'fts5':fts,'embeddings':args.embeddings},ensure_ascii=False))

if __name__=='__main__': main()
