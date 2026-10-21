"""Part A3: a risk-weighted sample through the full model path: the public gemma4:12b (Q4_K_M) on CPU via a local Ollama, the real go-live
prompt (prompt.py), the coordinator's real tools, and turn.run_turn (fast paths, the model, the claim guard, the one nudge, partial turns).

The loop mirrors Home Assistant's Ollama integration: one system message (the rendered prompt + the coordinator's API prompt), the chat
history, the tools in HA's Ollama format, num_ctx 8192 (HA's default), think off, the model's own sampling defaults (HA sets none), up to 10
tool rounds; each tool call goes to Coordinator.call_tool with the person's words, the turn identity and the last reply (as api.AtlasTool
does); each tool result goes back to the model as json.dumps(result) in a 'tool' message.

Every case starts from the canonical evening state (fixture.house()), so the system prompt is the same for every case and Ollama's prompt
cache holds (one cold prompt evaluation for the whole run). Timings are CPU timings (4 vCPU, no GPU), not the owner's GPU PC.

Usage: python -I rehearsal/model_run.py --sample rehearsal-set/model-sample.json [--out rehearsal-set/results/model.<label>.json] [--repeat 1]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys
import time
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fixture import PKG, ROOT, house, snapshot  # noqa: E402
from grade import grade, worst  # noqa: E402
from layers import SCENE_EXPECT, new_timers  # noqa: E402
from prompt import system_prompt  # noqa: E402

from atlas_household.turn import NUDGE, run_turn  # noqa: E402

OLLAMA = 'http://127.0.0.1:11434/api/chat'
MODEL = 'gemma4:12b'
OPTIONS = {'num_ctx': 8192}
MAX_TOOL_ROUNDS = 10


def chat(messages, tools):
    body = {'model': MODEL, 'messages': messages, 'tools': tools, 'stream': False, 'think': False, 'keep_alive': '24h', 'options': OPTIONS}
    req = urllib.request.Request(OLLAMA, json.dumps(body).encode(), {'Content-Type': 'application/json'})
    t = time.perf_counter()
    with urllib.request.urlopen(req, timeout=3600) as r:
        out = json.load(r)
    out['_wall'] = time.perf_counter() - t
    return out


class Conversation:
    """One HA conversation: the history the model sees, and the coordinator calls its tools make."""

    def __init__(self, h, conv_id: str):
        self.h, self.conv, self.sys = h, conv_id, system_prompt(h)
        self.messages = [{'role': 'system', 'content': self.sys}]
        self.person_text, self.turn, self.last_reply = '', None, None
        self.calls, self.timings, self.n = [], [], 0

    def person(self, text):
        self.n += 1
        self.person_text, self.turn = text, f'u{self.n}'
        prev = [m for m in self.messages if m['role'] == 'assistant' and m.get('content')]
        self.last_reply = prev[-1]['content'] if prev else None

    async def ask(self, text):
        """turn.run_turn's ask_model: the next user message (the person's words, or the guard's NUDGE), then the tool loop."""
        if text != NUDGE:
            self.person(text)
        self.messages.append({'role': 'user', 'content': text})
        for _ in range(MAX_TOOL_ROUNDS):
            r = await asyncio.get_running_loop().run_in_executor(None, chat, self.messages, self.h.tools)
            self.timings.append({k: r.get(k) for k in ('total_duration', 'prompt_eval_count', 'prompt_eval_cached_count', 'prompt_eval_duration',
                                                       'eval_count', 'eval_duration', '_wall')})
            msg = r['message']
            tcs = msg.get('tool_calls') or []
            am = {'role': 'assistant', 'content': msg.get('content') or ''}
            if tcs:
                am['tool_calls'] = tcs
            self.messages.append(am)
            if not tcs:
                return msg.get('content') or ''
            for tc in tcs:
                fn = tc['function']
                args = fn.get('arguments') or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except ValueError:
                        args = {'_unparsed': args}
                res = await self.h.coord.call_tool(fn['name'], args, conversation_id=self.conv, user_text=self.person_text, turn=self.turn,
                                                   last_reply=self.last_reply)
                self.calls.append({'tool': fn['name'], 'args': args, 'status': res.get('status'), 'reason': res.get('reason'), 'summary': res.get('summary')})
                self.messages.append({'role': 'tool', 'content': json.dumps(res)})
        return self.messages[-1].get('content') or ''


def run_case(req: dict) -> dict:
    h = house()
    conv = Conversation(h, 'rehearsal')
    ctx_out = []
    for turn in req.get('context') or []:          # a follow-up: the earlier turn runs through the real pipeline too
        o = h.loop.run_until_complete(run_turn(h.coord, turn['user'], conv.conv, conv.ask))
        if o['path'] == 'fast':                     # HA writes a fast reply into the chat log (conversation.py)
            conv.person(turn['user'])
            conv.messages += [{'role': 'user', 'content': turn['user']}, {'role': 'assistant', 'content': o['reply']}]
        else:
            conv.messages[-1]['content'] = o['reply']
        ctx_out.append({'user': turn['user'], 'reply': o['reply'], 'path': o['path']})
        h.advance(seconds=8)
    before, t_before = snapshot(h), {t['id'] for t in h.coord._pending()}
    n_calls, n_t = len(conv.calls), len(conv.timings)
    t0 = time.perf_counter()
    out = h.loop.run_until_complete(run_turn(h.coord, req['text'], conv.conv, conv.ask))
    wall = time.perf_counter() - t0
    if out['path'] == 'fast':
        conv.calls.append({'tool': out.get('tool'), 'args': out.get('args'), 'status': out['statuses'][0], 'reason': None, 'summary': out['reply']})
    after, timers = snapshot(h), new_timers(h, t_before)
    findings = grade(req, before, after, out['tool_results'], timers, out['reply'], SCENE_EXPECT, out['path'])
    tm = conv.timings[n_t:]
    return {'id': req['id'], 'text': req['text'], 'category': req['category'], 'tags': req['tags'], 'kind': req['expect']['kind'], 'context': ctx_out,
            'path': out['path'], 'first': out.get('first'), 'reply': out['reply'], 'claims': out.get('claims'), 'calls': conv.calls[n_calls:],
            'timers': timers, 'moved': sorted(set(e for e in after if after[e] != before.get(e))), 'findings': findings, 'grade': worst(findings),
            'wall_s': round(wall, 2), 'model_calls': len(tm), 'prompt_tokens': sum(t['prompt_eval_count'] or 0 for t in tm),
            'prompt_cached': sum(t.get('prompt_eval_cached_count') or 0 for t in tm), 'gen_tokens': sum(t['eval_count'] or 0 for t in tm),
            'prompt_eval_s': round(sum((t['prompt_eval_duration'] or 0) for t in tm) / 1e9, 2), 'gen_s': round(sum((t['eval_duration'] or 0) for t in tm) / 1e9, 2)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--sample', default=str(ROOT / 'rehearsal-set' / 'model-sample.json'))
    ap.add_argument('--label', default='current')
    ap.add_argument('--repeat', type=int, default=1)
    ap.add_argument('--only', default=None, help='comma-separated request ids')
    a = ap.parse_args(argv)
    sample = json.loads(pathlib.Path(a.sample).read_text(encoding='utf-8'))['requests']
    if a.only:
        keep = set(a.only.split(','))
        sample = [x for x in sample if x['id'] in keep]
    out = ROOT / 'rehearsal-set' / 'results' / f'model.{a.label}.jsonl'
    done = set()
    if out.exists():
        done = {(json.loads(l)['id'], json.loads(l).get('rep', 0)) for l in out.read_text(encoding='utf-8').splitlines() if l.strip()}
    with out.open('a', encoding='utf-8') as f:
        for rep in range(a.repeat):
            for req in sample:
                if (req['id'], rep) in done:
                    continue
                try:
                    rec = run_case(req)
                except Exception as ex:          # noqa: BLE001  recorded, the run goes on
                    rec = {'id': req['id'], 'text': req['text'], 'error': f'{type(ex).__name__}: {ex}', 'grade': 'ERROR'}
                rec['rep'], rec['package'] = rep, PKG
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')
                f.flush()
                print(rec['grade'], rec.get('path'), rec.get('wall_s'), repr(req['text'])[:70], '->', repr(rec.get('reply', rec.get('error')))[:110], flush=True)


if __name__ == '__main__':
    main()
