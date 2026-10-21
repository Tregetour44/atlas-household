"""Summaries for GAPS.md / README.md: the model runs (grades, findings by code and category, timings) and the hand review overrides.

Hand review (rehearsal-set/results/review.json): every model reply was read; an entry {id: {"grade": ..., "code": ..., "note": ...}} replaces
the automatic grade where the grader can't see the problem (an invented schedule) or saw one that isn't there. Usage:
  python -I rehearsal/summarise.py model.input.jsonl [model.patched.jsonl]
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fixture import ROOT  # noqa: E402

RES = ROOT / 'rehearsal-set' / 'results'
DONE = re.compile(r"\b(done|all set|sorted|I've|I have|switched|turned|closed|opened|set (?:to|at)|is now|are now)\b", re.I)


def load(name):
    rows = [json.loads(x) for x in (RES / name).read_text(encoding='utf-8').splitlines() if x.strip()]
    review = json.loads((RES / 'review.json').read_text(encoding='utf-8')) if (RES / 'review.json').exists() else {}
    label = name.split('.')[1]
    for r in rows:
        f = r.get('findings') or []
        # an older grader read a question as a claim ("Which blind would you like me to set to 30%?")
        stated = ' '.join(x for x in re.split(r"(?<=[.!?])\s+", r.get('reply') or '') if not x.rstrip().endswith('?'))
        f = [x for x in f if not (x['code'] == 'false_done' and not DONE.search(stated))]
        rv = (review.get(label) or {}).get(r['id'])
        if rv:
            f = [x for x in f if x['code'] != rv.get('drop')] + ([{'sev': rv['grade'], 'code': rv['code'], 'why': rv['note'], 'reviewed': True}] if rv.get('grade') else [])
        r['findings'] = f
        r['grade'] = next((s for s in ('MAJOR', 'MINOR', 'MISS') if any(x['sev'] == s for x in f)), 'OK') if 'error' not in r else 'ERROR'
    return rows


def summary(rows):
    out = {'cases': len(rows), 'grades': dict(Counter(r['grade'] for r in rows)), 'paths': dict(Counter(r.get('path') for r in rows))}
    codes = defaultdict(list)
    for r in rows:
        for f in r['findings']:
            if f['sev'] in ('MAJOR', 'MINOR'):
                codes[f"{f['sev']}:{f['code']}"].append(r['text'])
    out['findings'] = {k: {'n': len(v), 'examples': v[:6]} for k, v in sorted(codes.items())}
    return out


def main(argv):
    for name in argv or ['model.input.jsonl']:
        rows = load(name)
        print(name, json.dumps(summary(rows), indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main(sys.argv[1:])
