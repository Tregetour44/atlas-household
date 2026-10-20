"""Run cases through Gemma 4 12B (public gemma4:12b, Q4_K_M) on local Ollama, CPU, with the real go-live prompt rendered per case.

  python -B run_eval.py --arm current|candidate --cases cases/all.json --out results/<name>.jsonl [--repeats N] [--only ID,ID]

One turn = as the household hears it. current: model (with the coordinator's atlas_ tools) -> claim guard (core.guard_reply), exactly the live
path. candidate: fast_arithmetic -> model (atlas_ tools + atlas_calc) -> claim guard -> figure guard (calc.turn_figures: one nudge, then
unsupported sentences dropped). Acting tools are never executed here: a call is recorded and answered "not available in this test".
Ollama on 127.0.0.1 only; HA's defaults for the Ollama agent: think off, num_ctx 8192, the model's own sampling (temperature 1, top_k 64,
top_p 0.95), a fixed seed per case and repeat so a rerun is reproducible on the same build.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import calc  # noqa: E402
import energy_cards as E  # noqa: E402
import render as R  # noqa: E402
from atlas_household.core import guard_reply  # noqa: E402

MODEL = 'gemma4:12b'
URL = 'http://127.0.0.1:11434/api/chat'


def chat(messages, tools, seed):
    body = {'model': MODEL, 'messages': messages, 'tools': tools, 'stream': False, 'think': False, 'keep_alive': '60m',
            'options': {'num_ctx': 8192, 'seed': seed}}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.load(r)


def unload():
    """Free the model after each case: llama.cpp keeps prompt-cache snapshots (about 0.4 GB each) that otherwise exhaust RAM (OOM seen 10:39).
    Within a case the model stays loaded, so tool rounds and the figure nudge reuse the conversation's cache."""
    req = urllib.request.Request('http://127.0.0.1:11434/api/generate', data=json.dumps({'model': MODEL, 'keep_alive': 0}).encode(),
                                 headers={'Content-Type': 'application/json'})
    try:
        urllib.request.urlopen(req, timeout=120).read()
    except Exception:  # noqa: BLE001
        pass
    time.sleep(2)


def case_prompt(arm: str, c: dict) -> tuple[str, str, dict | None]:
    """(system prompt, cards text, cards) for a case. Codex 49 cases carry text facts (both arms); own cases carry structured inputs (cards
    for the candidate arm only: the current arm is the live prompt, which has no cards)."""
    now = datetime.fromisoformat(c['now']).astimezone(E.SYDNEY)
    cards = None
    if c.get('codex_facts'):
        text = 'Energy cards (worked out by Home Assistant; use these as given):\n' + '\n'.join(f'- {k}: {v}' for k, v in c['codex_facts'].items())
    elif arm == 'candidate':
        cards = E.build(now, c.get('energy', {}), c['question'])
        text = cards['text']
    else:
        text = ''
    return R.system_prompt(arm, now, c.get('house', {}), text), text, cards


async def one(arm: str, c: dict, repeat: int) -> dict:
    sysp, cards_text, _ = case_prompt(arm, c)
    seed = int(hashlib.sha256(f"{c['id']}:{repeat}".encode()).hexdigest()[:8], 16)
    tools = R.tool_specs(arm)
    rec = {'id': c['id'], 'arm': arm, 'repeat': repeat, 'question': c['question'], 'prompt_sha256': hashlib.sha256(sysp.encode()).hexdigest(),
           'tool_calls': [], 'path': 'model'}
    t0 = time.time()
    if arm == 'candidate':
        fast = calc.fast_arithmetic(c['question'])
        if fast:
            rec.update(first=fast, reply=fast, path='fast_arithmetic', seconds=round(time.time() - t0, 2), evidence=[], figures={})
            return rec
    messages = [{'role': 'system', 'content': sysp}]
    for turn in c.get('context', []):
        messages.append(turn)
    calc_results, summaries, evidence = [], [], []
    stats = {'prompt_eval_count': 0, 'eval_count': 0, 'rounds': 0}

    async def ask(text):
        messages.append({'role': 'user', 'content': text})
        for _ in range(5):
            d = await asyncio.to_thread(chat, messages, tools, seed)
            stats['rounds'] += 1
            stats['prompt_eval_count'] += d.get('prompt_eval_count', 0)
            stats['eval_count'] += d.get('eval_count', 0)
            msg = d['message']
            calls = msg.get('tool_calls') or []
            messages.append({k: msg[k] for k in ('role', 'content', 'tool_calls') if msg.get(k)})
            if not calls:
                return msg.get('content', '')
            for call in calls:
                fn = call['function']
                name, args = fn['name'], fn.get('arguments') or {}
                if name == calc.TOOL_NAME and arm == 'candidate':
                    res = calc.calc_tool(args, [calc.readings_part(sysp), c['question']] + summaries, calc_results)
                    if res['status'] == 'calculated':
                        calc_results.append(res['result'])
                        summaries.append(res['summary'])
                else:
                    res = {'status': 'denied', 'reason': 'evaluation', 'summary': "That isn't available in this test."}
                evidence.append((name, res['status']))
                rec['tool_calls'].append({'name': name, 'args': args, 'result': res})
                messages.append({'role': 'tool', 'tool_name': name, 'content': json.dumps(res)})
        return msg.get('content', '')

    first = await ask(c['question'])
    rec['calls_before_first'] = len(rec['tool_calls'])
    reply, claims = guard_reply(first, evidence)
    rec['first'], rec['claims'] = first, claims
    if arm == 'candidate':
        reply, fig = await calc.turn_figures(reply, [calc.readings_part(sysp), c['question']], ask, lambda: list(summaries))
        rec['figures'] = fig
        if fig.get('nudged'):
            rec['path'] = 'figure_nudged'
    rec.update(reply=reply, seconds=round(time.time() - t0, 1), stats=stats)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', required=True, choices=['current', 'candidate'])
    ap.add_argument('--cases', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--repeats', type=int, default=1)
    ap.add_argument('--only', default='')
    a = ap.parse_args()
    cases = json.loads(Path(a.cases).read_text())['cases']
    if a.only:
        keep = set(a.only.split(','))
        cases = [c for c in cases if c['id'] in keep]
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            r = json.loads(line)
            if not r.get('error'):
                done.add((r['id'], r['repeat']))
    since_unload = 0
    for rep in range(1, a.repeats + 1):
        todo = [c for c in cases if (c['id'], rep) not in done]
        for i, c in enumerate(todo):
            for attempt in (1, 2):
                try:
                    r = asyncio.run(one(a.arm, c, rep))
                    break
                except Exception as ex:  # noqa: BLE001  a failed trial stays in the denominator (after one retry)
                    r = {'id': c['id'], 'arm': a.arm, 'repeat': rep, 'question': c['question'], 'error': f'{type(ex).__name__}: {ex}', 'reply': ''}
                    unload()
                    since_unload = 0
            # unload between cases (memory), except when the next case has the identical system prompt (its cache is then reused); at most 6 in a row
            nxt = todo[i + 1] if i + 1 < len(todo) else None
            since_unload += 1
            if nxt is None or since_unload >= 6 or case_prompt(a.arm, nxt)[0] != case_prompt(a.arm, c)[0]:
                unload()
                since_unload = 0
            with out.open('a') as f:
                f.write(json.dumps(r, ensure_ascii=False, default=str) + '\n')
            print(f"{r['id']} r{rep} {r.get('seconds')}s {r.get('path')} | {r.get('reply', '')[:160]}", flush=True)


if __name__ == '__main__':
    main()
