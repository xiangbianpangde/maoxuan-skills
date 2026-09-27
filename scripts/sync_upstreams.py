#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / 'upstream/UPSTREAM_LOCK.json').read_text(encoding='utf-8'))
SUBMODULES = {
    'atomic': ROOT / 'vendor/kangarooking',
    'framework': ROOT / 'vendor/leezythu',
}


def run(*args: str) -> str:
    p = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    if p.returncode:
        detail = (p.stderr or p.stdout).strip()
        raise SystemExit(f"command failed ({' '.join(args)}): {detail}")
    return p.stdout.strip()


def main() -> None:
    if not (ROOT / '.gitmodules').exists():
        raise SystemExit('.gitmodules missing; repository integration is incomplete')

    run('git', 'submodule', 'sync', '--recursive')
    run('git', 'submodule', 'update', '--init', '--recursive')

    report = []
    for item in LOCK['sources']:
        sid = item['id']
        if sid not in SUBMODULES:
            continue
        path = SUBMODULES[sid]
        expected = item['commit']
        if not path.exists():
            raise SystemExit(f'submodule missing after update: {path.relative_to(ROOT)}')
        actual = run('git', '-C', str(path), 'rev-parse', 'HEAD')
        ok = actual == expected
        report.append({
            'id': sid,
            'path': path.relative_to(ROOT).as_posix(),
            'expected': expected,
            'actual': actual,
            'ok': ok,
        })
        if not ok:
            raise SystemExit(f'{sid} commit mismatch: expected {expected}, got {actual}')

    print(json.dumps({'ok': True, 'submodules': report}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
