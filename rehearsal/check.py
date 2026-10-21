"""Release check (run before a release goes live): every rehearsal request through the deterministic layers of THIS checkout, compared with
the expected outcomes and with the recorded baseline (rehearsal-set/baseline.json). Offline, about a minute.

Fails (exit 1) when:
  - a fast-path turn grades MAJOR or MINOR under the owner's bar (grade.py), or
  - a never-list turn the baseline refused whole is no longer matched by the never-list words, or
  - the which-blind scope widens for a request (more blinds than the baseline allowed), or a blind the words exclude becomes reachable.
Reports (no failure): requests that moved between the fast and the model path, never-list matches gained, scopes narrowed.
  python -I rehearsal/check.py                 # compare with the baseline
  python -I rehearsal/check.py --write-baseline   # after a reviewed change: record this checkout's decisions as the new baseline
The model half of the set (rehearsal-set/model-sample.json) needs a local Ollama with gemma4:12b: python -I rehearsal/model_run.py --label <release>
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fixture import ROOT  # noqa: E402
from grade import worst  # noqa: E402
from layers import run_one  # noqa: E402

BASE = ROOT / 'rehearsal-set' / 'baseline.json'


def decisions(recs):
    return {r['id']: {'path': r['path'], 'never': bool(r['never']), 'blind_scope': r['blind_scope'],
                      'fast': [[c[0], c[1], c[2]] for c in (r.get('fast') or {}).get('calls', [])]} for r in recs}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--write-baseline', action='store_true')
    a = ap.parse_args(argv)
    reqs = json.loads((ROOT / 'rehearsal-set' / 'requests.json').read_text(encoding='utf-8'))['requests']
    recs = [run_one(r) for r in reqs]
    now = decisions(recs)
    if a.write_baseline:
        BASE.write_text(json.dumps({'note': 'decisions of the deterministic layers per request (rehearsal/check.py --write-baseline)', 'decisions': now},
                                   indent=0, ensure_ascii=False) + '\n', encoding='utf-8')
        print(f'baseline written: {len(now)} requests')
        return 0
    base = json.loads(BASE.read_text(encoding='utf-8'))['decisions']
    by = {r['id']: r for r in reqs}
    fails, notes = [], []
    for r in recs:
        g = worst(r.get('fast_grade') or [])
        if r['path'] == 'fast' and g in ('MAJOR', 'MINOR'):
            fails.append(f"{g} on the fast path: {r['text']!r} {r['fast_grade']}")
        if any(f['code'] == 'excluded_blind_open' for f in r['layer']):
            fails.append(f"an excluded blind is reachable: {r['text']!r}")
        b = base.get(r['id'])
        if b is None:
            continue
        if b['never'] and not r['never']:
            fails.append(f"never-list no longer matches: {r['text']!r}")
        if not b['never'] and r['never']:
            notes.append(f"never-list now matches: {r['text']!r} ({r['never']!r})")
        if set(r['blind_scope'] or []) - set(b['blind_scope'] or []):
            fails.append(f"which-blind scope widened: {r['text']!r} {b['blind_scope']} -> {r['blind_scope']}")
        if b['path'] != r['path']:
            notes.append(f"path {b['path']} -> {r['path']}: {r['text']!r}")
    fast = sum(1 for r in recs if r['path'] == 'fast')
    print(f"{len(recs)} requests, {fast} fast ({fast / len(recs):.1%}); {len(fails)} failures, {len(notes)} notes")
    for x in fails:
        print('FAIL', x)
    for x in notes[:200]:
        print('note', x)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
