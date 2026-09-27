from __future__ import annotations
from pathlib import Path
import json, re, hashlib

ROOT = Path(__file__).resolve().parents[1]
VOL_MAP = {"第一卷":1,"第二卷":2,"第三卷":3,"第四卷":4,"第五卷":5,"第六卷":6,"第七卷":7}

def load_config():
    p = Path(__file__).with_name("config.json")
    if not p.exists():
        p = Path(__file__).with_name("config.example.json")
    cfg = json.loads(p.read_text(encoding="utf-8"))
    cfg["database"] = str((ROOT / cfg["database"]).resolve()) if not Path(cfg["database"]).is_absolute() else cfg["database"]
    cfg["corpus"] = str((ROOT / cfg["corpus"]).resolve()) if not Path(cfg["corpus"]).is_absolute() else cfg["corpus"]
    return cfg

def article_meta(path: Path):
    volume_name = path.parent.name
    volume = VOL_MAP.get(volume_name, 0)
    m = re.match(r"(\d+)[-_]?(.*)", path.stem)
    article_no = int(m.group(1)) if m else 0
    title = (m.group(2) if m else path.stem).strip(" -_")
    return volume, article_no, title

def paragraphs(text: str):
    # Markdown paragraph chunks: blank-line separated; tiny heading-only chunks attach to the next paragraph.
    raw=[p.strip() for p in re.split(r"\n\s*\n", text.replace("\r\n","\n")) if p.strip()]
    out=[]; pending=[]
    for p in raw:
        if p.startswith("#") and len(p) < 120:
            pending.append(p)
            continue
        if pending:
            p="\n".join(pending+[p]); pending=[]
        out.append(p)
    out.extend(pending)
    return out

def source_id(volume:int, article_no:int, para_no:int):
    return f"MX-V{volume:02d}-A{article_no:03d}-P{para_no:04d}"

def iter_corpus(corpus: Path):
    for path in sorted(corpus.glob("第*卷/*.md")):
        volume, article_no, title = article_meta(path)
        if not volume:
            continue
        text=path.read_text(encoding="utf-8", errors="replace")
        rel=path.relative_to(ROOT).as_posix()
        for i,p in enumerate(paragraphs(text),1):
            yield {"source_id":source_id(volume,article_no,i),"volume":volume,"article_no":article_no,"title":title,"path":rel,"para_no":i,"text":p}

def sha256_file(path: Path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20), b''):
            h.update(b)
    return h.hexdigest()
