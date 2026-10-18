"""One Atlas turn, in the order the household hears it (pure Python; no HA imports). Used by the claim-guarded agent (conversation.py) and by
the Atlas-side project's scored runners, so a benchmark scores exactly this logic (the Atlas-side project's request, 18 Oct 21:5x):

  1. the deterministic timer path (fastpath.parse_timer): a strict timer request naming exactly one light or scene is scheduled through the
     coordinator's atlas_schedule, and the model is not asked;
  2. otherwise the model answers (it may call atlas_ tools; the coordinator records each result for this conversation);
  3. the claim guard (core.guard_reply) on the reply, against this turn's tool results;
  4. if it caught a claim and NO tool ran at all, the model is asked once more (NUDGE) and the second reply is guarded the same way.

ask_model(text) -> awaitable str: send `text` as the next user message in the same conversation and return the model's final reply. Any
atlas_ tool it calls must go through the same coordinator (so the results are recorded). other_tools() -> bool: whether a tool that isn't
atlas_ ran since the turn started (HA's agent reads its chat log; a runner with only atlas_ tools passes nothing). call_tool defaults to
coord.call_tool; HA passes its own wrapper so the device calls carry the person's context.
"""
from __future__ import annotations

from .core import NEVER_WORDS, guard_reply
from .fastpath import parse_timer

NUDGE = "You didn't call a tool. If the request needs one, call the right atlas_ tool now; otherwise say plainly that you can't do it."


async def run_turn(coord, text: str, conversation_id: str, ask_model, *, other_tools=None, call_tool=None, now_local=None) -> dict:
    """Returns {'reply', 'path' ('fast' | 'model' | 'nudged'), 'claims' (unbacked claim kinds left after the guard), 'statuses', 'first',
    'tool_results'}: tool_results lists (tool, args, result) for every atlas_ call the coordinator handled in this conversation during the turn
    (the fast path's own call included), e.g. a timer's due_local and handle for the Atlas-side project's scorer."""
    t0 = coord.mono()
    fast = parse_timer(text, coord.handles, now_local or coord.now().astimezone(coord.tz))
    if fast is not None:
        try:
            if call_tool is None:
                res = await coord.call_tool('atlas_schedule', fast, conversation_id=conversation_id, user_text=text)
            else:
                res = await call_tool('atlas_schedule', fast)
        except Exception as ex:      # noqa: BLE001  [B16-06] said honestly, never HA's generic error
            coord._log('fast_timer', 'error', conversation=conversation_id, args=fast, error=f'{type(ex).__name__}: {ex}')
            res = {'status': 'tool_error', 'summary': "Something went wrong, so I didn't set that timer."}
        reply = res.get('summary') or "I couldn't set that timer."
        coord._log('fast_timer', res.get('status'), conversation=conversation_id, args=fast)
        return {'reply': reply, 'path': 'fast', 'claims': [], 'statuses': [res.get('status')], 'first': None, 'args': fast,
                'tool_results': coord.results_since(t0, conversation_id) or [('atlas_schedule', fast, res)]}

    def evidence():
        # (tool, status) pairs, so a lights result can't back a blind claim [cloud review 1, M8]
        ev = coord.evidence_since(t0, conversation_id)
        if other_tools is not None and other_tools():
            ev.append((None, 'external_tool'))  # another tool ran: never say "I haven't changed anything" [R13-06]
        return ev

    first = await ask_model(text)
    ev = evidence()
    statuses = [st for _, st in ev]
    reply, bad = guard_reply(first, ev)
    path = 'model'
    if bad and not statuses and not NEVER_WORDS.search(text or ''):
        # never when the person's words are on the never-list: the whole turn is refused there, and a nudge could only push a partial
        # action (B16-01). The guarded reply stands.
        # C0e triage 1 (the Atlas-side project): the model claimed without calling any tool. Ask ONCE to call the tool or say it can't, then guard again.
        second = await ask_model(NUDGE)
        ev = evidence()
        statuses = [st for _, st in ev]
        reply, bad = guard_reply(second, ev)
        path = 'nudged'
        coord._log('claim_guard', 'nudged once', conversation=conversation_id, first=first[:300], second=second[:300], claims=bad)
    elif bad:
        coord._log('claim_guard', 'reply rewritten', conversation=conversation_id, claims=bad, original=first[:300])
    return {'reply': reply, 'path': path, 'claims': bad, 'statuses': statuses, 'evidence': ev, 'first': first,
            'tool_results': coord.results_since(t0, conversation_id)}
