"""One Atlas turn, in the order the household hears it (pure Python; no HA imports). Used by the claim-guarded agent (conversation.py) and by
the Atlas-side project's scored runners, so a benchmark scores exactly this logic (the Atlas-side project's request, 18 Oct 21:5x):

  1. the deterministic timer path (fastpath.parse_timer): a strict timer request naming exactly one light or scene is scheduled through the
     coordinator's atlas_schedule, and the model is not asked;
  1b. the deterministic level path (fastpath.parse_level, R18): a strict level or on/off request naming exactly one light handle is sent
     through the coordinator's atlas_lights, and the model is not asked;
  2. otherwise the model answers (it may call atlas_ tools; the coordinator records each result for this conversation);
  3. the claim guard (core.guard_reply) on the reply, against this turn's tool results;
  4. if it caught a claim and NO tool ran at all, the model is asked once more (NUDGE) and the second reply is guarded the same way.
  5. an empty final reply is never passed through (C0g G12, the Atlas-side project 18 Oct): the coordinator's own summaries of this turn are spoken instead.

ask_model(text) -> awaitable str: send `text` as the next user message in the same conversation and return the model's final reply. Any
atlas_ tool it calls must go through the same coordinator (so the results are recorded). other_tools() -> bool: whether a tool that isn't
atlas_ ran since the turn started (HA's agent reads its chat log; a runner with only atlas_ tools passes nothing). call_tool defaults to
coord.call_tool; HA passes its own wrapper so the device calls carry the person's context.
"""
from __future__ import annotations

import re

from .core import _SENT, NEVER_WORDS, guard_reply
from .fastpath import parse_level, parse_timer

NUDGE = "You didn't call a tool. If the request needs one, call the right atlas_ tool now; otherwise say plainly that you can't do it."
_SOON = re.compile(r"\s*,?\s+\b(?:yet|for now|just yet|at the moment|right now)\b(?=\s*[.!,]|\s*$)", re.I)
_CANT = re.compile(r"\b(can't|cannot|can not|unable|not able|don't have)\b", re.I)


def person_turn(items: list, user_text: str = '', turn=None, last_reply=None):
    """The person's words for a tool call, from the chat log as (kind, text, created) items, kind 'user' | 'assistant' | other: the last user
    turn that isn't the claim guard's NUDGE [B16-01], its identity (index:created) and Atlas's reply just before it (for the yes check)."""
    for i in range(len(items) - 1, -1, -1):
        kind, text, created = items[i]
        if kind == 'user' and text == NUDGE:
            continue                 # the claim guard's one nudge is not the person's words: use the turn it belongs to
        if kind == 'user':
            user_text, turn = text, f'{i}:{created}'
            for j in range(i - 1, -1, -1):
                if items[j][0] == 'assistant' and items[j][1]:
                    last_reply = items[j][1]
                    break
                if items[j][0] == 'user':
                    break
            break
    return user_text, turn, last_reply


def plain_never_refusal(reply: str) -> str:
    """G56 (the Atlas-side project, C0g): a Never-list thing is never possible, so a refusal of it doesn't say "yet" or "for now"."""
    return ' '.join(_SOON.sub('', s) if _CANT.search(s) else s for s in re.split(r"(?<=[.!?])\s+", reply or '')).strip()


EMPTY_NOTHING_RAN = "Sorry, I didn't catch that."
EMPTY_UNSUMMARISED = "I can't confirm all of that."


_ASKS = {'needs_confirmation', 'needs_choice'}
_TO_MODEL = re.compile(r"^(?:Ask\b.*|.*\bwait for a yes\b.*)$", re.I)


def _spoken(r: dict) -> str:
    """A result as the person should hear it: its question when it has one ('Ask exactly: "…" and wait for a yes.' is for the model), else
    its summary without the sentences addressed to the model ("Ask which.")."""
    if (r.get('question') or '').strip() and (r.get('status') in _ASKS or r.get('reason') in ('no_plain_yes', 'question_not_asked')):
        return r['question'].strip()                     # the question still waiting for the person's yes [R18b-03]
    sents = re.split(r"(?<=[.!?])\s+", (r.get('summary') or '').strip())
    return ' '.join(s for s in sents if s and not _TO_MODEL.match(s)).strip()


def empty_reply_fallback(results: list, evidence: list) -> str:
    """What to say when the model's final reply is empty (C0g G12: brighten denied twice, then brightness 80 done, then ''). The summaries of
    the results that sent something (done, scheduled, failed...) in call order; if none sent, the last result's summary (why it was refused);
    if no atlas_ result has a summary but a tool ran, "I can't confirm all of that."; if nothing ran, "Sorry, I didn't catch that."."""
    asks = lambda r: r.get('status') in _ASKS or r.get('reason') in ('no_plain_yes', 'question_not_asked')   # noqa: E731
    sent = ([_spoken(r) for _n, _a, r in results if r.get('status') in _SENT and not asks(r)]
            + [_spoken(r) for _n, _a, r in results if asks(r)])     # an open question is said too, and last, so the reply ends on it [R18-02, R18b-03, R18c-04]
    said = list(dict.fromkeys(x for x in sent if x))        # a repeated identical summary is said once
    if not said:
        last = [_spoken(r) for _n, _a, r in results]
        last = [x for x in last if x]
        said = [last[-1]] if last else []
    if said:
        return ' '.join(said)
    return EMPTY_UNSUMMARISED if evidence else EMPTY_NOTHING_RAN


async def run_turn(coord, text: str, conversation_id: str, ask_model, *, other_tools=None, call_tool=None, now_local=None) -> dict:
    """Returns {'reply', 'path' ('fast' | 'model' | 'nudged'), 'claims' (unbacked claim kinds left after the guard), 'statuses', 'first',
    'tool_results'}: tool_results lists (tool, args, result) for every atlas_ call the coordinator handled in this conversation during the turn
    (the fast path's own call included), e.g. a timer's due_local and handle for the Atlas-side project's scorer."""
    t0 = coord.mono()
    fast = parse_timer(text, coord.handles, now_local or coord.now().astimezone(coord.tz), getattr(coord, 'timer_scenes', True))
    tool, label, sorry = 'atlas_schedule', 'fast_timer', "I didn't set that timer."
    if fast is None:
        fast = parse_level(text, coord.handles)
        tool, label, sorry = 'atlas_lights', 'fast_level', "I didn't change anything."
    if fast is not None:
        try:
            if call_tool is None:
                res = await coord.call_tool(tool, fast, conversation_id=conversation_id, user_text=text)
            else:
                res = await call_tool(tool, fast)
        except Exception as ex:      # noqa: BLE001  [B16-06] said honestly, never HA's generic error
            coord._log(label, 'error', conversation=conversation_id, args=fast, error=f'{type(ex).__name__}: {ex}')
            res = {'status': 'tool_error', 'summary': f"Something went wrong, so {sorry}"}
        reply = res.get('summary') or f"Sorry, {sorry}"
        coord._log(label, res.get('status'), conversation=conversation_id, args=fast)
        return {'reply': reply, 'path': 'fast', 'claims': [], 'statuses': [res.get('status')], 'first': None, 'args': fast, 'tool': tool,
                'tool_results': coord.results_since(t0, conversation_id) or [(tool, fast, res)]}

    def evidence():
        # (tool, status) pairs, so a lights result can't back a blind claim [cloud review 1, M8]
        ev = coord.evidence_since(t0, conversation_id)
        if other_tools is not None and other_tools():
            ev.append((None, 'external_tool'))  # another tool ran: never say "I haven't changed anything" [R13-06]
        return ev

    scope = coord._blind_scope(text) if hasattr(coord, '_blind_scope') else None
    expect = {'blind': len(scope)} if scope else None          # how many blinds the person's words named, for "all the blinds" [GQ-01]
    first = await ask_model(text)
    ev = evidence()
    statuses = [st for _, st in ev]
    reply, bad = guard_reply(first, ev, coord.results_since(t0, conversation_id), expect)
    path = 'model'
    if bad and not statuses and not NEVER_WORDS.search(text or ''):
        # never when the person's words are on the never-list: the whole turn is refused there, and a nudge could only push a partial
        # action (B16-01). The guarded reply stands.
        # C0e triage 1 (the Atlas-side project): the model claimed without calling any tool. Ask ONCE to call the tool or say it can't, then guard again.
        second = await ask_model(NUDGE)
        ev = evidence()
        statuses = [st for _, st in ev]
        reply, bad = guard_reply(second, ev, coord.results_since(t0, conversation_id), expect)
        path = 'nudged'
        coord._log('claim_guard', 'nudged once', conversation=conversation_id, first=first[:300], second=second[:300], claims=bad)
    elif bad:
        coord._log('claim_guard', 'reply rewritten', conversation=conversation_id, claims=bad, original=first[:300])
    results = coord.results_since(t0, conversation_id)
    ok = [r for _n, _a, r in results if r.get('status') in ('done', 'undone', 'skipped_already', 'scheduled', 'cancelled')]
    open_ = [r for _n, _a, r in results if r.get('status') in ('needs_choice', 'needs_confirmation', 'failed', 'not_verified', 'tool_error')]
    if ok and open_:
        # a PARTIAL turn (something done, something asked or failed): the model's words aren't trusted; say exactly what happened, in call
        # order, ending on the open question (the lead project 20 Oct 21:5x: "closed both" was a false done) [GQ-01, GQ-02, GQ-05]
        reply = empty_reply_fallback(results, ev)
        coord._log('claim_guard', 'partial turn said from results', conversation=conversation_id, original=first[:300])
    elif bad and '?' not in (reply or ''):      # a rewritten reply still asks the "which blind?" that came back [AM2-03, R5-03, GQ-06]
        for _n, _a, r in results:
            q = (r.get('summary') or '').split("It isn't clear which blind. ")[-1]
            if r.get('reason') == 'which_blind' and q.endswith('?'):
                reply = f"{(reply or '').strip()} {q}".strip()
                break
    if NEVER_WORDS.search(text or ''):
        reply = plain_never_refusal(reply)
    if not (reply or '').strip():
        reply = empty_reply_fallback(results, ev)
        coord._log('empty_reply', 'fallback spoken', conversation=conversation_id, path=path, reply=reply[:300])
    return {'reply': reply, 'path': path, 'claims': bad, 'statuses': statuses, 'evidence': ev, 'first': first, 'tool_results': results, 'expect': expect}
