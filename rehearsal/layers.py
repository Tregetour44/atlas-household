"""Part A2: every rehearsal request through the deterministic layers, on the fixture (no model, no network).

For each request it records the decisions the layers make from the words alone, and what they would do to the tool calls a model might make:
  path        'fast' (the deterministic path handled it whole; graded in full under the owner's bar) or 'model'
  fast        the fast path's tool calls, statuses and the reply as spoken
  never       the never-list match on the person's words (the whole turn refused), and the text it matched
  blind_scope the blinds the person's words name (Coordinator._blind_scope), or None (unclear: the coordinator asks which)
  intended    the calls the words mean (from the expected outcome; for a never-list turn, its allowed half), run through the coordinator
              with the person's words: allowed, or refused and why
  open_blinds blind handles the coordinator would let a model move for these words, outside what the words allow (over-reach envelope)
  open_floors floor-wide light handles the coordinator would accept for these words, outside what the words allow
  fast_grade  findings for a fast-path turn; layer findings (envelope holes, over-refusals) in `layer`

Usage: python -I rehearsal/layers.py [--set rehearsal-set/requests.json] [--out rehearsal-set/results/layers.<label>.json] [--label current]
ATLAS_PKG=<dir with atlas_household> selects the coordinator copy (e.g. the input branch, for a before/after comparison).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys
import time
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fixture import EVENING, PKG, ROOT, build_targets, house, snapshot  # noqa: E402
from grade import grade, worst  # noqa: E402

from atlas_household.core import NEVER_WORDS  # noqa: E402
from atlas_household.turn import run_turn  # noqa: E402

TARGETS = build_targets()
HANDLES = TARGETS['handles']
SCENE_EXPECT = {h: t.get('expect') or {} for h, t in HANDLES.items() if t['kind'] == 'scene'}
BLIND_HANDLES = [h for h, t in HANDLES.items() if t['kind'] == 'blind' and t.get('enabled', True)]
FLOORS = ['upstairs_lights', 'ground_floor_lights', 'outside_lights']


def handles_for(E: list[str], kind: str) -> list[str]:
    """The fewest enabled handles of this kind whose entities exactly cover E (greedy, largest first)."""
    E = set(E)
    cands = sorted([(h, set(t['entity_ids'])) for h, t in HANDLES.items() if t['kind'] == kind and t.get('enabled', True) and set(t['entity_ids']) <= E],
                   key=lambda x: (-len(x[1]), x[0].endswith('_lights') is False, x[0]))
    out, left = [], set(E)
    for h, es in cands:
        if es <= left:
            out.append(h)
            left -= es
    return out if not left else []


def calls_for(act: dict) -> list[tuple[str, dict]]:
    op, E = act['op'], act['entities']
    if op.startswith('scene:'):
        return [('atlas_scene', {'recipe_handle': op.split(':')[1]})]
    if E and E[0].startswith('cover.'):
        hs = handles_for(E, 'blind')
        if op.startswith('pos:'):
            return [('atlas_blind', {'target_handle': h, 'operation': 'position', 'position_percent': int(op.split(':')[1])}) for h in hs]
        return [('atlas_blind', {'target_handle': h, 'operation': op}) for h in hs]
    hs = handles_for(E, 'light')
    if op.startswith('level:'):
        n = op.split(':')[1]
        return [('atlas_lights', {'target_handle': h, 'operation': 'brightness', 'brightness_percent': 50 if n == 'any' else int(n)}) for h in hs]
    return [('atlas_lights', {'target_handle': h, 'operation': op}) for h in hs]


def timer_calls(req) -> list[tuple[str, dict]]:
    out = []
    for t in req['expect'].get('timers') or []:
        for h in handles_for(t['entities'], 'light'):
            a = {'target_handle': h, 'operation': t['op']}
            a.update({'in_minutes': t['minutes']} if 'minutes' in t else {'at_time': t['at']})
            out.append(('atlas_schedule', a))
    return out


def new_timers(h, before_ids: set) -> list[dict]:
    from atlas_household.fake import SYDNEY
    out = []
    for t in h.coord._pending():
        if t['id'] in before_ids:
            continue
        from datetime import datetime
        due = datetime.fromisoformat(t['due_at']).astimezone(SYDNEY)
        made = datetime.fromisoformat(t['created_at'])
        out.append({'entities': sorted(HANDLES[t['handle']]['entity_ids']), 'op': t['operation'], 'due_hhmm': due.strftime('%H:%M'),
                    'in_minutes': round((datetime.fromisoformat(t['due_at']) - made).total_seconds() / 60), 'handle': t['handle']})
    return out


async def _never_called(_text):
    raise RuntimeError('model')


def replay_context(h, req, conv):
    """A follow-up's earlier turn: through the real deterministic path if it takes it, else the canned assistant reply (no tool)."""
    for turn in req.get('context') or []:
        async def canned(_t, reply=turn['assistant']):
            return reply
        h.loop.run_until_complete(run_turn(h.coord, turn['user'], conv, canned))
        h.advance(seconds=5)


def run_one(req: dict) -> dict:
    text = req['text']
    rec = {'id': req['id'], 'text': text, 'category': req['category'], 'kind': req['expect']['kind']}
    # --- the turn itself: fast path or not ---
    h = house()
    conv = 'rehearsal'
    replay_context(h, req, conv)
    before, t_before = snapshot(h), {t['id'] for t in h.coord._pending()}
    t0 = time.perf_counter()
    try:
        out = h.loop.run_until_complete(run_turn(h.coord, text, conv, _never_called))
        path = out['path']
    except RuntimeError as ex:
        if str(ex) != 'model':
            raise
        out, path = None, 'model'
    rec['path'] = path
    if path == 'fast':
        rec['fast_ms'] = round((time.perf_counter() - t0) * 1000, 3)
        results = out['tool_results']
        rec['fast'] = {'calls': [[n, a, r.get('status'), r.get('reason')] for n, a, r in results], 'reply': out['reply']}
        after, timers = snapshot(h), new_timers(h, t_before)
        rec['fast_grade'] = grade(req, before, after, results, timers, out['reply'], SCENE_EXPECT, 'fast')
    h.loop.close()
    # --- what the layers decide from the words ---
    m = NEVER_WORDS.search(text)
    rec['never'] = m.group(0) if m else None
    h = house()
    sc = h.coord._blind_scope(text)
    rec['blind_scope'] = sorted(sc) if sc else None
    h.loop.close()
    exp = req['expect']
    layer = []
    # intended calls (the allowed half, for a never-list turn)
    acts = exp.get('would_be') if exp.get('never') else exp.get('acts')
    calls = [c for a in acts or [] if a['entities'] or a['op'].startswith('scene:') for c in calls_for(a)] + timer_calls(req)
    res = []
    for name, args in calls:
        h = house()
        replay_context(h, req, conv)
        r = h.call(name, args, user_text=text, conversation_id=conv)
        res.append([name, args, r.get('status'), r.get('reason')])
        h.loop.close()
    rec['intended'] = res
    if exp.get('never') or exp['kind'] == 'refuse_never':
        leaks = [x for x in res if x[2] not in ('denied', 'needs_choice')]
        if not rec['never']:
            layer.append({'sev': 'HOLE', 'code': 'never_words_miss', 'why': 'the never-list does not match these words; only the model keeps the turn whole'})
        if leaks:
            layer.append({'sev': 'HOLE', 'code': 'never_allowed_half_runs', 'why': f'the coordinator would run {leaks}'})
    elif exp['kind'] in ('act', 'timer', 'partial'):
        refused = [x for x in res if x[2] in ('denied', 'needs_choice')]
        if refused:
            layer.append({'sev': 'OVER', 'code': 'intended_refused', 'why': f'the coordinator refuses the intended call(s) {refused}'})
    # over-reach envelope: blinds and floors a model could move for these words, outside what they allow
    allowed = set(exp.get('allowed') or [])
    open_b = []
    if not rec['never']:
        for bh in BLIND_HANDLES:
            es = set(HANDLES[bh]['entity_ids'])
            if es <= allowed:
                continue
            h = house()
            r = h.call('atlas_blind', {'target_handle': bh, 'operation': 'close' if h.state(next(iter(es)))['attributes'].get('current_position') else 'open'},
                       user_text=text, conversation_id=conv)
            if r.get('status') not in ('denied', 'needs_choice', 'failed'):
                open_b.append(bh)
            h.loop.close()
        open_f = []
        for fh in FLOORS:
            es = set(HANDLES[fh]['entity_ids'])
            if es <= allowed:
                continue
            h = house()
            r = h.call('atlas_lights', {'target_handle': fh, 'operation': 'off'}, user_text=text, conversation_id=conv)
            if r.get('status') not in ('denied', 'needs_choice', 'failed'):
                open_f.append(fh)
            h.loop.close()
        rec['open_blinds'], rec['open_floors'] = open_b, open_f
        if set().union(*[set(HANDLES[b]['entity_ids']) for b in open_b] or [set()]) & set(exp.get('excluded') or []):
            layer.append({'sev': 'HOLE', 'code': 'excluded_blind_open', 'why': f'the coordinator would move an excluded blind via {open_b}'})
    rec['layer'] = layer
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--set', default=str(ROOT / 'rehearsal-set' / 'requests.json'))
    ap.add_argument('--label', default='current')
    ap.add_argument('--out', default=None)
    a = ap.parse_args(argv)
    reqs = json.loads(pathlib.Path(a.set).read_text(encoding='utf-8'))['requests']
    t0 = time.time()
    recs = [run_one(r) for r in reqs]
    by = {r['id']: r for r in reqs}
    fast = [x for x in recs if x['path'] == 'fast']
    sev = Counter(worst(x.get('fast_grade') or []) for x in fast)
    summary = {'label': a.label, 'package': PKG, 'requests': len(recs), 'fast': len(fast), 'fast_share': round(len(fast) / len(recs), 4),
               'fast_by_category': dict(Counter(x['category'] for x in fast).most_common()), 'fast_grades': dict(sev),
               'never_matched_in_never_turns': sum(1 for x in recs if by[x['id']]['expect'].get('never') and x['never']),
               'never_turns': sum(1 for x in recs if by[x['id']]['expect'].get('never')),
               'never_matched_in_other_turns': sum(1 for x in recs if not by[x['id']]['expect'].get('never') and x['never']),
               'layer_findings': dict(Counter(f"{f['sev']}:{f['code']}" for x in recs for f in x['layer'])),
               'fast_ms_median': sorted(x['fast_ms'] for x in fast)[len(fast) // 2] if fast else None, 'seconds': round(time.time() - t0, 1)}
    out = pathlib.Path(a.out or ROOT / 'rehearsal-set' / 'results' / f'layers.{a.label}.json')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'summary': summary, 'records': recs}, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
