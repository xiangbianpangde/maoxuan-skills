#!/usr/bin/env python3
from pathlib import Path
import json, hashlib, re
ROOT=Path(__file__).resolve().parents[1]
VOL={'第一卷':1,'第二卷':2,'第三卷':3,'第四卷':4,'第五卷':5}
rows=[]
for p in sorted((ROOT/'毛选md').glob('第*卷/*.md')):
    m=re.match(r'(\d+)[-_]?(.*)',p.stem); n=int(m.group(1)) if m else 0; title=(m.group(2) if m else p.stem).strip(' -_')
    b=p.read_bytes(); rows.append({'volume':VOL.get(p.parent.name,0),'article_no':n,'title':title,'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)})
out=ROOT/'evidence/corpus-manifest.generated.json'; out.write_text(json.dumps({'schema_version':'1.0','files':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(out)
