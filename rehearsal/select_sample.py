"""Part A3: choose the risk-weighted sample for the model path, from the layer run (only requests the model decides: path 'model').

Weights follow the owner's bar: where a model error would be MAJOR and no deterministic layer stops it, the case is taken first:
  - a never-list turn the never-list words miss (only the model keeps the turn whole), then never-list turns the words catch (the reply must
    still not claim the allowed half);
  - blinds: exclusions, vague references, indirect wording, positions, timers (the model picks the blind and the direction);
  - partial turns (allowed + not yet): the model must not hide the part it can't do;
  - lights where a room handle would over-reach a single light, vague and all-lights requests, steps, relative and indirect wording;
  - scenes against greetings, questions and statements (no action), timers the fast path doesn't take, multi-action and run-on turns,
    follow-ups, speech-to-text errors, and every owner phrasing.
Seeded. Usage: python -I rehearsal/select_sample.py [--layers rehearsal-set/results/layers.current.json] [--seed 7]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fixture import ROOT  # noqa: E402

QUOTA = [  # (category or predicate name, n)
    ('hole:never_words_miss:ordinary', 18), ('hole:never_words_miss:adversarial', 5), ('never_mixed', 12), ('never_pronoun', 9), ('never_alone', 3),
    ('never_lookalike', 5), ('blind_exclusion', 8), ('blind_vague', 7), ('blind_indirect', 5), ('blind_named', 5), ('blind_position', 4),
    ('blind_pair', 2), ('blind_all', 3), ('blind_timer', 3), ('blind_timer_mixed', 2), ('blind_question', 2), ('partial_not_yet', 10),
    ('not_yet_ac', 3), ('not_yet_media', 2), ('not_yet_scene', 2), ('not_yet_other', 2), ('scene', 8), ('greeting', 3), ('scene_timer', 2),
    ('scene_question', 2), ('light_onoff:single_in_room', 6), ('light_vague', 3), ('light_all', 2), ('light_step', 3), ('light_relative', 2),
    ('light_indirect', 3), ('light_timer', 4), ('light_timer_trap', 2), ('light_timer_vague', 2), ('question', 6), ('question_state', 5),
    ('question_readonly', 4), ('multi', 7), ('followup', 7), ('stt', 8), ('owner', 99),
]
SINGLE_IN_ROOM = {'family room lamp', 'mirror glow', 'galley pendant', 'galley ceiling', 'flood lamp', 'yard spot', 'attic lamp', 'sunroom floor lamp', 'front downlight'}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--layers', default=str(ROOT / 'rehearsal-set' / 'results' / 'layers.current.json'))
    ap.add_argument('--seed', type=int, default=7)
    a = ap.parse_args(argv)
    reqs = {r['id']: r for r in json.loads((ROOT / 'rehearsal-set' / 'requests.json').read_text(encoding='utf-8'))['requests']}
    recs = [x for x in json.loads(pathlib.Path(a.layers).read_text(encoding='utf-8'))['records'] if x['path'] == 'model']
    r = random.Random(a.seed)
    r.shuffle(recs)
    chosen, why = [], {}

    def take(pred, n, label):
        got = 0
        for x in recs:
            if got >= n:
                break
            if x['id'] in why or not pred(x):
                continue
            why[x['id']] = label
            chosen.append(x['id'])
            got += 1
    for name, n in QUOTA:
        if name.startswith('hole:never_words_miss'):
            adv = name.endswith('adversarial')
            take(lambda x, adv=adv: any(f['code'] == 'never_words_miss' for f in x['layer']) and (('adversarial' in reqs[x['id']]['tags']) == adv), n, name)
        elif name == 'light_onoff:single_in_room':
            take(lambda x: x['category'] == 'light_onoff' and any(s in x['text'] for s in SINGLE_IN_ROOM), n, name)
        elif name == 'stt':
            take(lambda x: x['category'].startswith('stt_'), n, name)
        else:
            take(lambda x, c=name: x['category'] == c, n, name)
    out = {'seed': a.seed, 'from': a.layers, 'count': len(chosen), 'requests': [{**reqs[i], 'why_sampled': why[i]} for i in chosen]}
    (ROOT / 'rehearsal-set' / 'model-sample.json').write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    from collections import Counter
    print(len(chosen), dict(Counter(why.values())))


if __name__ == '__main__':
    main()
