"""Part B1/B3: where the time goes, fast path against model path, and the coverage gain. Reads the layer runs and the model run; measures the
deterministic overhead (fast path, guard, truth check) in-process. CPU timings (4 vCPU, no GPU): the owner's PC runs Gemma on a GPU, so the
model figures here are an upper bound; the token counts carry over.

Usage: python -I rehearsal/latency.py [--before layers.input.json] [--after layers.patched.json] [--model model.input.jsonl]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import statistics
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fixture import ROOT, house  # noqa: E402

from atlas_household.turn import run_turn  # noqa: E402

RES = ROOT / 'rehearsal-set' / 'results'


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))] if xs else None


def overhead(n=300) -> dict:
    """In-process cost of the deterministic layers on a model turn: run_turn with an instant scripted model (no tool), so what is timed is the
    fast-path parsing that falls through, the guard and the truth check (state reads from the fake backend)."""
    texts = ['could you sort out the office lights', 'is the sunroom blind open?', 'turn the office lights off and open the garage', 'good night, see you tomorrow']
    out = []
    h = house()

    async def model(_t):
        return "The office lights are on at 80%."
    for i in range(n):
        t0 = time.perf_counter()
        h.loop.run_until_complete(run_turn(h.coord, texts[i % len(texts)], f'c{i}', model))
        out.append((time.perf_counter() - t0) * 1000)
    return {'median_ms': round(statistics.median(out), 2), 'p90_ms': round(pct(out, 90), 2)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--before', default=str(RES / 'layers.input.json'))
    ap.add_argument('--after', default=str(RES / 'layers.patched.json'))
    ap.add_argument('--model', default=str(RES / 'model.input.jsonl'))
    a = ap.parse_args(argv)
    b = json.loads(pathlib.Path(a.before).read_text(encoding='utf-8'))
    f = json.loads(pathlib.Path(a.after).read_text(encoding='utf-8'))
    m = [json.loads(x) for x in pathlib.Path(a.model).read_text(encoding='utf-8').splitlines() if x.strip()]
    m = [x for x in m if x.get('path') in ('model', 'nudged')]
    fast_ms = [x['fast_ms'] for x in f['records'] if x['path'] == 'fast']
    by = {x['id']: x for x in b['records']}
    newly = [x for x in f['records'] if x['path'] == 'fast' and by.get(x['id'], {}).get('path') != 'fast']
    from collections import Counter
    out = {
        'coverage': {'requests': f['summary']['requests'], 'fast_before': b['summary']['fast'], 'fast_after': f['summary']['fast'],
                     'share_before': b['summary']['fast_share'], 'share_after': f['summary']['fast_share'],
                     'newly_fast_by_category': dict(Counter(x['category'] for x in newly).most_common())},
        'fast_path_cpu': {'n': len(fast_ms), 'median_ms': round(statistics.median(fast_ms), 2), 'p90_ms': round(pct(fast_ms, 90), 2),
                          'note': 'parse + coordinator call + read-back against the in-memory fake (device time not included; it is the same on both paths)'},
        'model_path_cpu': {'n': len(m), 'median_s': round(statistics.median(x['wall_s'] for x in m), 1), 'p90_s': round(pct([x['wall_s'] for x in m], 90), 1),
                           'model_calls_median': statistics.median(x['model_calls'] for x in m),
                           'model_calls_mean': round(statistics.mean(x['model_calls'] for x in m), 2),
                           'nudged_share': round(sum(1 for x in m if x['path'] == 'nudged') / len(m), 3),
                           'uncached_prompt_tokens_median': statistics.median(x['prompt_tokens'] - x['prompt_cached'] for x in m),
                           'generated_tokens_median': statistics.median(x['gen_tokens'] for x in m),
                           'prompt_eval_s_median': round(statistics.median(x['prompt_eval_s'] for x in m), 1),
                           'generation_s_median': round(statistics.median(x['gen_s'] for x in m), 1),
                           'note': 'gemma4:12b Q4_K_M on 4 vCPU, prompt cache warm (5.9k-token system prompt cached); a cold prompt costs ~246 s here'},
        'deterministic_overhead_on_model_turns': overhead(),
    }
    (RES / 'latency.json').write_text(json.dumps(out, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
