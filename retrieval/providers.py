from __future__ import annotations
import json, os, urllib.request

def _post_json(url, payload, api_key):
    data=json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req=urllib.request.Request(url, data=data, method='POST', headers={'Content-Type':'application/json','Authorization':f'Bearer {api_key}'})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode('utf-8'))

def embeddings(texts, cfg):
    api_key=os.getenv(cfg['api_key_env'],'')
    if not api_key:
        raise RuntimeError(f"missing environment variable: {cfg['api_key_env']}")
    url=cfg['base_url'].rstrip('/') + '/embeddings'
    obj=_post_json(url, {'model':cfg['model'],'input':texts}, api_key)
    return [x['embedding'] for x in sorted(obj['data'], key=lambda x:x.get('index',0))]

def rerank(query, docs, cfg):
    api_key=os.getenv(cfg['api_key_env'],'')
    if not api_key:
        return None
    url=cfg['base_url'].rstrip('/') + '/rerank'
    payload={'model':cfg['model'],'query':query,'documents':docs,'top_n':min(cfg.get('top_n',8),len(docs)),'return_documents':False}
    obj=_post_json(url,payload,api_key)
    return obj.get('results') or obj.get('data')
