#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'evidence/skill-source-map.generated.json'
OUT = ROOT / 'eval/evidence-coverage.generated.json'


def ratio(a: int, b: int) -> float | None:
    return round(a / b, 4) if b else None


def main() -> None:
    if not SRC.exists():
        raise SystemExit('missing evidence map; run python3 scripts/build_evidence_map.py first')

    data = json.loads(SRC.read_text(encoding='utf-8'))
    rows = []
    for slug, rec in sorted(data.get('skills', {}).items()):
        chapters = rec.get('source_chapter_matches', [])
        quotes = rec.get('reading_quote_matches', [])
        chapter_hits = sum(bool(x.get('matches')) for x in chapters)
        chapter_not_found = sum(x.get('local_source_status') == 'not_found' for x in chapters)
        quote_hits = sum(bool(x.get('matches')) for x in quotes)
        quote_source_not_found = sum(x.get('match_status') == 'source_not_found' for x in quotes)
        quote_unresolved = sum(x.get('match_status') == 'unresolved' for x in quotes)
        exact = sum(x.get('match_status') == 'exact' for x in quotes)
        ellipsis = sum(x.get('match_status') == 'ellipsis' for x in quotes)
        fuzzy = sum(x.get('match_status') == 'fuzzy' for x in quotes)
        local_quote_targets = len(quotes) - quote_source_not_found
        rows.append({
            'skill': slug,
            'status': rec.get('status', 'unknown'),
            'declared_chapters': len(chapters),
            'matched_chapters': chapter_hits,
            'chapters_not_found_locally': chapter_not_found,
            'chapter_match_rate': ratio(chapter_hits, len(chapters)),
            'reading_quotes': len(quotes),
            'matched_quotes': quote_hits,
            'exact_quotes': exact,
            'ellipsis_quotes': ellipsis,
            'fuzzy_quotes': fuzzy,
            'quote_sources_not_found_locally': quote_source_not_found,
            'quotes_unresolved_with_local_source': quote_unresolved,
            'quote_match_rate': ratio(quote_hits, len(quotes)),
            'local_quote_match_rate': ratio(quote_hits, local_quote_targets),
            'has_any_chapter_evidence': chapter_hits > 0,
            'has_any_quote_evidence': quote_hits > 0,
        })

    active = [x for x in rows if x['status'] != 'vendor-missing']
    summary = {
        'skills_total': len(rows),
        'skills_with_vendor': len(active),
        'skills_with_any_chapter_evidence': sum(x['has_any_chapter_evidence'] for x in active),
        'skills_with_any_quote_evidence': sum(x['has_any_quote_evidence'] for x in active),
        'declared_chapters': sum(x['declared_chapters'] for x in active),
        'matched_chapters': sum(x['matched_chapters'] for x in active),
        'chapters_not_found_locally': sum(x['chapters_not_found_locally'] for x in active),
        'reading_quotes': sum(x['reading_quotes'] for x in active),
        'matched_quotes': sum(x['matched_quotes'] for x in active),
        'exact_quotes': sum(x['exact_quotes'] for x in active),
        'ellipsis_quotes': sum(x['ellipsis_quotes'] for x in active),
        'fuzzy_quotes': sum(x['fuzzy_quotes'] for x in active),
        'quote_sources_not_found_locally': sum(x['quote_sources_not_found_locally'] for x in active),
        'quotes_unresolved_with_local_source': sum(x['quotes_unresolved_with_local_source'] for x in active),
    }
    summary['chapter_match_rate'] = ratio(summary['matched_chapters'], summary['declared_chapters'])
    local_quote_targets=summary['reading_quotes']-summary['quote_sources_not_found_locally']
    summary['quote_match_rate'] = ratio(summary['matched_quotes'], summary['reading_quotes'])
    summary['local_quote_match_rate'] = ratio(summary['matched_quotes'], local_quote_targets)

    result = {'schema_version': '2.0', 'summary': summary, 'skills': rows}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(OUT)


if __name__ == '__main__':
    main()
