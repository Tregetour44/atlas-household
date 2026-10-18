"""Cloud review 2: a generated adversarial pack (seeded generator, fixed seed; no third-party dependency, so it runs in the owner's offline suite).

Four families, each case asserting an invariant of the README / the owner's rules:
  NeverListMixing   allowed commands mixed with forbidden intents (varied wording, order, punctuation, case, synonyms; lights, scenes, blinds,
                    timers, cancel, undo, confirm), and never-list words in the map's own handle names and labels (aliases):
                    the whole turn is refused and nothing is sent, queued or cancelled.
  ClaimGuardPairs   replies with and without tool evidence across past, present, verbless, acknowledgement, future, timer, cancel, undo,
                    question, conditional and negated shapes: an unbacked claim never gets through, a backed honest reply is never rewritten,
                    the head never says "I haven't changed anything." when something was sent, and the rewrite holds no claim of its own.
  Timers            relative and absolute times, am/pm and bare hours (the fast path), noon and midnight, Australia/Sydney DST edges, the 24 h
                    cap, list, cancel, firing at the due time and the restart notice, against an independent oracle (enumerated instants).
  OverReach         floor-wide and whole-outside groups for words that name a room, a lamp, another floor, or "all the lights in <room>";
                    the fast path's similar names (singular, plural, lamp vs lights).

Every failing case is shrunk greedily to its smallest still-failing form, and each test reports the distinct minimal examples.
`python -I tests/test_cloud_review_2_generated.py --report` prints the case counts and the minimised failures (used for REVIEW.md).
"""
from __future__ import annotations

import copy
import json
import pathlib
import random
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'custom_components'))
from atlas_household.core import Coordinator, guard_reply  # noqa: E402
from atlas_household.fake import SYDNEY, TARGETS, FakeHouse, MemoryStore  # noqa: E402
from atlas_household.fastpath import parse_timer  # noqa: E402

SEED = 20261018
HAVENT = "I haven't changed anything."
CANT = "I can't confirm all of that."
COUNTS: dict[str, int] = {}
FAILURES: dict[str, list[str]] = {}
HAVE_TZ = getattr(SYDNEY, 'key', None) == 'Australia/Sydney'


def _targets() -> dict:
    """The synthetic map plus one reviewed scene (the map ships none reviewed), so the scene paths are exercised too."""
    t = json.loads(TARGETS.read_text(encoding='utf-8'))
    t['handles']['galley_cooking'].update(members=['light.galley_ceiling', 'light.galley_pendant'],
                                          expect={'light.galley_ceiling': {'state': 'on', 'brightness_percent': 100},
                                                  'light.galley_pendant': {'state': 'on', 'brightness_percent': 100}})
    return t


TARGETS_PLUS = _targets()


def house(**kw) -> FakeHouse:
    return FakeHouse(targets=copy.deepcopy(TARGETS_PLUS), **kw)


def shrink(case: dict, steps, fails) -> dict:
    """Greedy shrink: apply each simplification while the case still fails; repeat until nothing changes."""
    changed = True
    while changed:
        changed = False
        for step in steps:
            for smaller in step(case):
                if smaller != case and fails(smaller):
                    case, changed = smaller, True
                    break
    return case


def record(family: str, n: int, failures: list[str]) -> None:
    COUNTS[family] = COUNTS.get(family, 0) + n
    FAILURES.setdefault(family, [])
    for f in failures:
        if f not in FAILURES[family]:
            FAILURES[family].append(f)


def report(tc: unittest.TestCase, family: str, failures: list[str]) -> None:
    if failures:
        tc.fail(f"{len(failures)} minimal failing case(s) in {family}:\n  " + '\n  '.join(failures[:40]))


# =============================================================== never-list ===============================================================
# Allowed commands: (tool, args, words, setup). setup prepares the house so the command would really act (or cancel/undo something).
ALLOWED = [
    ('atlas_lights', {'target_handle': 'office_lights', 'operation': 'on'}, 'turn on the office light', None),
    ('atlas_lights', {'target_handle': 'attic_lamp', 'operation': 'off'}, 'switch the attic lamp off', 'attic_on'),
    ('atlas_lights', {'target_handle': 'family_room_lights', 'operation': 'dim'}, 'dim the family room lights', 'family_on'),
    ('atlas_lights', {'target_handle': 'deck_lights', 'operation': 'brightness', 'brightness_percent': 40}, 'deck lights to 40 percent', None),
    ('atlas_scene', {'recipe_handle': 'galley_cooking'}, 'run the galley cooking scene', None),
    ('atlas_blind', {'target_handle': 'office_blind', 'operation': 'open'}, 'open the office blind', None),
    ('atlas_schedule', {'target_handle': 'entry_lights', 'operation': 'on', 'in_minutes': 10}, 'entry lights on in 10 minutes', None),
    ('atlas_schedule', {'target_handle': 'galley_cooking', 'operation': 'on', 'at_time': '21:00'}, 'galley cooking scene at 9 pm', None),
    ('atlas_schedule', {'target_handle': 'office_blind', 'operation': 'open', 'in_minutes': 30}, 'open the office blind in half an hour', None),
    ('atlas_cancel', {}, 'cancel that', 'timer'),
    ('atlas_undo', {}, 'undo that', 'undo'),
    ('atlas_confirm', None, 'yes', 'confirm'),
]
# Forbidden intents, by never-list subject. Each must refuse the whole turn wherever it appears.
FORBIDDEN = {
    'lock': ['unlock the front door', 'lock the back door', 'lock up', 'unbolt the door', 'bolt the side door', 'secure the doors',
             'slide the deadbolt', 'unlock it', 'engage the latch', 'relock the door', 'unlock the smart lock'],
    'alarm': ['arm the alarm', 'disarm the alarm', 'turn off the alarm', 'arm the house', 'set the security system', 'arm stay mode',
              'arm night mode', 'set the house to armed', 'arm the perimeter', 'dis-arm the system', 'silence the siren', 'put the house in away mode'],
    'garage/door/gate opener': ['open the garage', 'close the garage door', 'garage up', 'pop the garage', 'raise the roller door', 'open the gate',
                                'shut the driveway gate', 'open the door', 'roll up the garage', 'open the carport', 'lift the tilt door',
                                'trigger the door strike', 'hit the door release', 'let me in', 'buzz me in', 'open the shed'],
    'energy/battery/inverter': ['set the battery to backup', 'charge the battery', 'turn off the inverter', 'check the powerwall', 'stop charging',
                                'turn off the car charger', 'charge the car', 'set home storage to backup', 'sell power back', 'restart the power-wall',
                                'show the energy use'],
    'solar': ['turn off the solar', 'check the PV', 'clean the photovoltaics', 'how are the rooftop panels doing'],
    'tariff/export/grid': ['change the tariff', 'stop the export', 'go off grid', 'switch to off-peak', 'use the time-of-use rate',
                           'set the feed-in limit', 'check the shoulder rate', 'read the smart meter'],
}
CONNECT = [' and ', ', then ', ' & ', '. Also ', ', ', ' + ', ' plus ', '; ', ' and also ', '\n', ' - ', ' then ']
PREFIX = ['', 'hey atlas, ', 'can you ', 'please ', 'Atlas ', 'ok so ']
SUFFIX = ['', '.', '!', ' please', '?', ' thanks', ' now']
CASES = [str, str.upper, str.title, str.capitalize]
ORDER = ['allowed_first', 'forbidden_first']


def _setup(h: FakeHouse, kind: str | None) -> dict:
    extra = {}
    if kind == 'attic_on':
        h.set('light.attic_lamp', 'on')
    elif kind == 'family_on':
        for e in h.targets['handles']['family_room_lights']['entity_ids']:
            h.set(e, 'on', brightness_percent=80)
    elif kind == 'timer':
        assert h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 10}, user_text='office lights off in 10 minutes')['status'] == 'scheduled'
    elif kind == 'undo':
        assert h.call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'on'}, user_text='office light on')['status'] == 'done'
    elif kind == 'confirm':
        q = h.call('atlas_blind', {'target_handle': 'office_blind', 'operation': 'open'}, user_text='open the office blind')
        extra = {'confirmation': q['confirmation'], 'last_reply': q['question']}
    return extra


def never_text(c: dict) -> str:
    a, f = ALLOWED[c['allowed']][2], c['forbidden']
    body = (a + c['connect'] + f) if c['order'] == 'allowed_first' else (f + c['connect'] + a)
    return CASES[c['case']](c['prefix'] + body + c['suffix'])


def never_fails(c: dict) -> str | None:
    """None if the invariant holds: the turn is refused whole and nothing is sent, queued or cancelled."""
    tool, args, _, setup = ALLOWED[c['allowed']]
    h = house()
    extra = _setup(h, setup)
    calls, tasks = len(h.calls), json.dumps(h.coord.data['tasks'], sort_keys=True)
    if tool == 'atlas_confirm':
        args = {'confirmation': extra['confirmation']}
    r = h.call(tool, dict(args), user_text=never_text(c), last_reply=extra.get('last_reply'))
    if (r['status'], r.get('reason')) != ('denied', 'never_list'):
        return f"{r['status']}"
    if len(h.calls) != calls or json.dumps(h.coord.data['tasks'], sort_keys=True) != tasks:
        return 'acted'
    return None


def never_steps():
    def plain(c):
        yield {**c, 'prefix': ''}
        yield {**c, 'suffix': ''}
        yield {**c, 'case': 0}
        yield {**c, 'connect': ' and '}
        yield {**c, 'order': 'allowed_first'}
        yield {**c, 'allowed': 0}
    return [plain]


class NeverListMixing(unittest.TestCase):
    def test_mixed_turns_are_refused_whole(self):
        rng = random.Random(SEED)
        phrases = [(k, p) for k, ps in FORBIDDEN.items() for p in ps]
        cases = []
        for i in range(1100):
            k, p = phrases[i % len(phrases)]            # every forbidden phrase many times, in varied company
            cases.append({'subject': k, 'forbidden': p, 'allowed': rng.randrange(len(ALLOWED)), 'connect': rng.choice(CONNECT),
                          'prefix': rng.choice(PREFIX), 'suffix': rng.choice(SUFFIX), 'case': rng.randrange(len(CASES)), 'order': rng.choice(ORDER)})
        bad = []
        for c in cases:
            if never_fails(c):
                m = shrink(c, never_steps(), never_fails)
                tool = ALLOWED[m['allowed']][0]
                bad.append(f"[{m['subject']}] {tool} ran for {never_text(m)!r} -> {never_fails(m)}")
        bad = sorted(set(bad))
        record('never-list mixing', len(cases), bad)
        report(self, 'never-list mixing', bad)

    def test_control_allowed_alone_still_acts(self):
        """The fix must not refuse ordinary turns, including ones with near-miss words."""
        near = ['', ' by the garage light', ' and the security lights', ' and the family room door blind', ' and the office roller blind',
                ' and let the light in', ' and the armchair lamp', ' at peak brightness', ' near the carport lights', ' and the deck lights']
        rng = random.Random(SEED + 1)
        n, bad = 0, []
        for i in range(120):
            tool, args, words, setup = ALLOWED[i % len(ALLOWED)]
            text = CASES[rng.randrange(len(CASES))](rng.choice(PREFIX) + words + rng.choice(near) + rng.choice(SUFFIX))
            h = house()
            extra = _setup(h, setup)
            a = {'confirmation': extra['confirmation']} if tool == 'atlas_confirm' else dict(args)
            r = h.call(tool, a, user_text=text, last_reply=extra.get('last_reply'))
            n += 1
            if r.get('reason') == 'never_list':
                bad.append(f'{tool} refused for {text!r}')
        record('never-list controls', n, sorted(set(bad)))
        report(self, 'never-list controls', sorted(set(bad)))

    def test_map_aliases_on_the_never_list_do_not_load(self):
        """A handle whose name or label is on the never-list must not load, whatever entity id or reviewed class it carries ("via aliases")."""
        words = ['Garage door', 'Front door lock', 'Gate opener', 'Alarm siren', 'Battery', 'Inverter', 'Solar export', 'Tariff switch',
                 'Garage', 'Driveway gate', 'Deadbolt', 'Roller door', 'Car charger', 'Powerwall', 'Door strike']
        n, bad = 0, []
        for w in words:
            slug = re.sub(r'[^a-z0-9]+', '_', w.lower()).strip('_')
            for kind, ent, cls in (('blind', 'cover.blind_motor_9', 'shutter'), ('light', 'light.relay_3', None)):
                if w == 'Garage' and kind == 'light':
                    continue                                  # a light called "Garage" is the garage light
                for handle, label in ((slug, 'Relay three'), ('relay_three', w), (slug, w)):
                    t = {'handles': {handle: {'kind': kind, 'label': label, 'entity_ids': [ent]}}, 'reviewed_covers': {ent: cls} if cls else {}}
                    n += 1
                    try:
                        Coordinator(t, None, MemoryStore(), None, SYDNEY)
                    except ValueError:
                        continue
                    bad.append(f'{kind} handle {handle!r} label {label!r} loads')
        # shrink: report only the label-only and handle-only forms (the combined one adds nothing)
        bad = [b for b in bad if "label 'Relay three'" in b or "handle 'relay_three'" in b]
        record('never-list aliases', n, bad)
        report(self, 'never-list aliases', bad)


# =============================================================== claim guard ===============================================================
THINGS = {
    'light': [('the office lights', 'are'), ('the attic lamp', 'is'), ('the lights', 'are'), ('the family room downlights', 'are')],
    'blind': [('the office blind', 'is'), ('the family room blinds', 'are')],
    'scene': [('the Galley Cooking scene', 'is')],
}
BACK = {'light': ('atlas_lights', 'done'), 'blind': ('atlas_confirm', 'done'), 'scene': ('atlas_scene', 'done')}
WRONG = {'light': [('atlas_confirm', 'done'), ('atlas_blind', 'needs_confirmation'), ('atlas_lights', 'skipped_already'), ('atlas_schedule', 'scheduled')],
         'blind': [('atlas_lights', 'done'), ('atlas_blind', 'needs_confirmation'), ('atlas_scene', 'done'), ('atlas_schedule', 'scheduled')],
         'scene': [('atlas_lights', 'done'), ('atlas_confirm', 'done'), ('atlas_scene', 'skipped_already')]}
OK = ['', 'Okay, ', 'Sure, ', 'Got it, ', 'Alright, ', 'No problem, ', 'Right, ']
ADV = ['', 'just ', 'now ', 'gone ahead and ', 'also ']
SENT = {'done', 'undone', 'scheduled', 'cancelled', 'not_verified', 'failed_sent', 'tool_error', 'external_tool'}   # something changed


def cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def _verbs(thing):
    return {'light': [('turned off', 'off'), ('switched on', 'on'), ('dimmed', 'dimmed'), ('turned on', 'on'), ('switched off', 'off')],
            'blind': [('closed', 'closed'), ('opened', 'open'), ('lowered', 'closed'), ('raised', 'open')],
            'scene': [('activated', 'active'), ('started', 'running'), ('run', 'running')]}[thing]


def claim_reply(c: dict) -> str:
    """Render one claim of a shape about a thing. Every shape here claims something happened (or will, as a timer)."""
    obj, be = THINGS[c['thing']][c['obj']]
    verb, state = _verbs(c['thing'])[c['verb'] % len(_verbs(c['thing']))]
    have = 'has' if be == 'is' else 'have'
    ok, adv = OK[c['ok']], ADV[c['adv']]
    pp = 'ran' if verb == 'run' else verb
    s = c['shape']
    if s == 'past':
        return f"{ok}I've {adv}{verb} {obj}." if verb != 'run' else f"{ok}I've {adv}run {obj}."
    if s == 'past_simple':
        return f"{ok}I {pp} {obj}."
    if s == 'present_now':
        return cap(f"{ok}{obj} {be} now {state}.")
    if s == 'been':
        return cap(f"{ok}{obj} {have} been {verb if verb != 'run' else 'started'}.")
    if s == 'now_been':
        return cap(f"{ok}{obj} {have} now been {verb if verb != 'run' else 'started'}.")
    if s == 'ack_thing':
        return f"Done, {obj} {be} now {state}."
    if s == 'verbless':
        return cap(f"{ok}{obj.replace('the ', '', 1)} {state}.")
    if s == 'future_now':
        base = {'turned off': 'turn off', 'switched on': 'switch on', 'dimmed': 'dim', 'turned on': 'turn on', 'switched off': 'switch off',
                'closed': 'close', 'opened': 'open', 'lowered': 'lower', 'raised': 'raise', 'activated': 'activate', 'started': 'start', 'run': 'run'}[verb]
        return f"{ok}I'll {base} {obj} now."
    if s == 'pronoun':
        return f"{ok}I've {adv}{verb} it."
    raise KeyError(s)


SHAPES_ACTION = ['past', 'past_simple', 'present_now', 'been', 'now_been', 'ack_thing', 'verbless', 'future_now']
TIMER_PAST = ["Timer set: {o} off at 9 pm.", "I've set a timer: {o} off at 9 pm.", "Timer's set for 9 pm.", "I've set {o} to turn off at 9 pm.",
              "I've scheduled {o} to turn off at 9 pm.", "I've started a 10-minute timer for {o}."]
# what WILL happen: a timer list backs these as well as a timer just set [R13-03]
TIMER_FUTURE = ["{O} will turn off at 9 pm.", "{O} will switch off in 10 minutes.", "In 10 minutes, {o} will turn off.", "They'll switch off at 9 pm.",
                "{O} will be off at 9 pm.", "It'll turn off in 10 minutes.", "{O} {are} set to turn off at 9 pm.", "{O} {are} scheduled to turn off at 9 pm.",
                "Got it, {s} off at 9 pm.", "Okay, {s} off in 10 minutes."]
CANCEL = ["I've cancelled the timer.", "Timer cancelled.", "The 9 pm timer has been cancelled.", "Done, I've cancelled the timer.", "That's cancelled.",
          "Cancelled the 9 pm timer."]
UNDO = ["I've undone that.", "Undone.", "That's been undone.", "Okay, I've reverted that."]
ACK = ['Done!', 'All done.', 'All set.', "There you go!", 'Taken care of.', 'Consider it done.']
ACK_TIMER = ["Done! {O} will switch off at 9 pm.", "All set, {o} will turn off in 10 minutes.", "All done, {o} will switch off at 9 pm."]
NONCLAIM = ["Shall I turn off {o}?", "Would you like me to close {o}?", "Do you want {o} off?", "I'll close {o} once you say yes.",
            "I haven't turned off {o}.", "I couldn't close {o}.", "{O} were turned off at 9 pm.", "I can't change {o} right now.",
            "Should I switch {o} on, since you're heading out?", "I can turn {o} off if you'd like."]


def _fill(tpl: str, obj: str, be: str) -> str:
    return (tpl.replace('{O}', cap(obj)).replace('{o}', obj).replace('{s}', obj.replace('the ', '', 1)).replace('{S}', cap(obj.replace('the ', '', 1))).replace('{are}', be))


def _ev_form(ev: list, bare: bool) -> list:
    return [st for _, st in ev] if bare else ev


def guard_case_fails(c: dict) -> str | None:
    """The invariant for one (reply, evidence) pair. c['want'] is 'pass' (honest: unchanged) or 'catch' (unbacked: rewritten)."""
    reply, ev = c['reply'], _ev_form(c['ev'], c.get('bare', False))
    out, bad = guard_reply(reply, ev)
    sts = {x if isinstance(x, str) else x[1] for x in ev}
    if c['want'] == 'pass':
        return None if (out, bad) == (reply, []) else f'honest reply rewritten to {out!r}'
    if not bad or out == reply:
        return 'unbacked claim passed'
    if out.startswith(HAVENT) and sts & SENT:
        return f"says {HAVENT!r} although something was sent"
    again = guard_reply(out, ev)
    if again[1]:
        return f'the rewrite still claims {again[1]}: {out!r}'
    return None


def guard_steps():
    def simpler(c):
        yield {**c, 'bare': False}
        if len(c['ev']) > 1:
            for i in range(len(c['ev'])):
                yield {**c, 'ev': c['ev'][:i] + c['ev'][i + 1:]}
        r = c['reply']
        for p in OK[1:] + ['Done, ']:
            if r.startswith(p):
                yield {**c, 'reply': cap(r[len(p):])}
        for a in ADV[1:]:
            if a in r:
                yield {**c, 'reply': r.replace(a, '', 1)}
    return [simpler]


def gen_guard_cases(rng: random.Random) -> list[dict]:
    cases = []
    noise = [[], [('atlas_scheduled', 'scheduled_list')], [('atlas_lights', 'skipped_already')]]
    # 1. action shapes about one thing: honest with its own result, caught with none or a wrong one
    for _ in range(520):
        thing = rng.choice(list(THINGS))
        c = {'thing': thing, 'obj': rng.randrange(len(THINGS[thing])), 'verb': rng.randrange(5), 'ok': rng.randrange(len(OK)),
             'adv': rng.randrange(len(ADV)), 'shape': rng.choice(SHAPES_ACTION)}
        if c['shape'] in ('present_now', 'verbless', 'ack_thing', 'been', 'now_been', 'future_now'):
            c['adv'] = 0
        reply = claim_reply(c)
        extra = rng.choice(noise)
        if rng.random() < 0.5:
            cases.append({'family': f"action/{c['shape']}/{thing}", 'reply': reply, 'ev': [BACK[thing]] + extra, 'want': 'pass', 'bare': False})
        else:
            ev = rng.choice([[], [rng.choice(WRONG[thing])], [('atlas_lights', 'failed')], [('atlas_blind', 'denied')]]) + extra
            cases.append({'family': f"action/{c['shape']}/{thing}", 'reply': reply, 'ev': ev, 'want': 'catch', 'bare': False})
    # 2. a pronoun claim ("I've closed it.") in a turn where the lights were done and the blind still waits for its yes [M8 by pronoun]
    for _ in range(80):
        c = {'thing': 'blind', 'obj': 0, 'verb': rng.randrange(4), 'ok': rng.randrange(len(OK)), 'adv': rng.randrange(len(ADV)), 'shape': 'pronoun'}
        lead = rng.choice(['', "I've turned off the office lights. ", 'The office lights are off. '])
        cases.append({'family': 'pronoun/blind', 'reply': lead + claim_reply(c), 'ev': [('atlas_lights', 'done'), ('atlas_blind', 'needs_confirmation')],
                      'want': 'catch'})
        cases.append({'family': 'pronoun/blind', 'reply': lead + claim_reply(c), 'ev': [('atlas_lights', 'done'), ('atlas_confirm', 'done')],
                      'want': 'pass'})
    # 3. timers, cancel, undo, acknowledgements
    for _ in range(330):
        thing = 'light'
        obj, be = THINGS[thing][rng.randrange(len(THINGS[thing]))]
        kind = rng.choice(['timer_past', 'timer_future', 'cancel', 'undo', 'ack', 'ack_timer'])
        tpl = rng.choice({'timer_past': TIMER_PAST, 'timer_future': TIMER_FUTURE, 'cancel': CANCEL, 'undo': UNDO, 'ack': ACK, 'ack_timer': ACK_TIMER}[kind])
        reply = _fill(tpl, obj, be)
        good = {'timer_past': [('atlas_schedule', 'scheduled')], 'timer_future': [('atlas_schedule', 'scheduled')],
                'cancel': [('atlas_cancel', 'cancelled')], 'undo': [('atlas_undo', 'undone')], 'ack': [rng.choice([BACK['light'], ('atlas_schedule', 'scheduled')])],
                'ack_timer': [('atlas_schedule', 'scheduled')]}[kind]
        wrong = {'timer_past': [[], [('atlas_scheduled', 'scheduled_list')], [('atlas_lights', 'done')], [('atlas_schedule', 'denied')]],
                 'timer_future': [[], [('atlas_lights', 'done')], [('atlas_schedule', 'needs_choice')]],
                 'cancel': [[], [('atlas_scheduled', 'scheduled_list')], [('atlas_cancel', 'needs_choice')], [('atlas_schedule', 'scheduled')]],
                 'undo': [[], [('atlas_lights', 'done')], [('atlas_undo', 'denied')], [('atlas_scheduled', 'scheduled_list')]],
                 'ack': [[], [('atlas_lights', 'skipped_already')], [('atlas_blind', 'needs_confirmation')], [('atlas_lights', 'denied')]],
                 'ack_timer': [[], [('atlas_schedule', 'needs_choice')], [('atlas_scheduled', 'scheduled_list')]]}[kind]
        if kind == 'timer_future' and rng.random() < 0.3:
            good = [('atlas_scheduled', 'scheduled_list')]          # a list backs what WILL happen [R13-03]
        if rng.random() < 0.5:
            cases.append({'family': f'{kind}', 'reply': reply, 'ev': good, 'want': 'pass', 'bare': rng.random() < 0.3})
        else:
            w = rng.choice(wrong)
            if kind == 'ack_timer' and w == [('atlas_scheduled', 'scheduled_list')]:
                w = []                                              # "Done!" with only a list read is unbacked; keep the case unambiguous
            cases.append({'family': f'{kind}', 'reply': reply, 'ev': w, 'want': 'catch', 'bare': False})
    # 4. replies that claim nothing pass with any evidence
    for _ in range(150):
        thing = rng.choice(['light', 'blind'])
        obj, be = THINGS[thing][rng.randrange(len(THINGS[thing]))]
        reply = _fill(rng.choice(NONCLAIM), obj, be)
        if '{O} were' in reply or ' were turned off at 9 pm' in reply:
            reply = reply.replace(' were ', ' was ') if be == 'is' else reply
        ev = rng.choice([[], [('atlas_blind', 'needs_confirmation')], [('atlas_lights', 'denied')], [('atlas_scheduled', 'scheduled_list')]])
        cases.append({'family': 'nonclaim', 'reply': reply, 'ev': ev, 'want': 'pass'})
    return cases


# Known and held (the owner's R17 review): an acknowledgement in the same clause as a thing ("All set, the office lights will turn off ...")
# is matched against the lights' tools, not the timer's. Kept out of the new-findings test and asserted on its own.
def _r17_01(c: dict) -> bool:
    return c['family'] == 'ack_timer' and c['want'] == 'pass' and not c['reply'].startswith('Done!')


class ClaimGuardPairs(unittest.TestCase):
    def run_family(self, name, cases):
        bad = []
        for c in cases:
            if guard_case_fails(c):
                m = shrink(c, guard_steps(), guard_case_fails)
                ev = _ev_form(m['ev'], m.get('bare', False))
                bad.append(f"[{m['family']}] {m['reply']!r} with {ev}: {guard_case_fails(m)}")
        bad = sorted(set(bad))
        record(name, len(cases), bad)
        report(self, name, bad)

    def test_pairs(self):
        cases = [c for c in gen_guard_cases(random.Random(SEED + 2)) if not _r17_01(c)]
        self.run_family('claim guard pairs', cases)

    def test_known_R17_01_ack_with_a_thing_backed_by_a_timer(self):
        """KNOWN (R17-01): held by the owner; patch 0005 proposes a fix."""
        cases = [c for c in gen_guard_cases(random.Random(SEED + 2)) if _r17_01(c)]
        self.assertTrue(cases)
        self.run_family('claim guard pairs (known R17-01)', cases)


# =============================================================== timers ===============================================================
def _instants(d, hh: int, mm: int) -> list[datetime]:
    """Every real instant whose Sydney wall clock reads d hh:mm (0, 1 or 2 of them), found by scanning UTC minutes: no fold arithmetic."""
    naive = datetime(d.year, d.month, d.day, hh, mm)
    guess = naive.replace(tzinfo=timezone(timedelta(hours=10))).astimezone(timezone.utc)
    out = []
    for off in range(-120, 121, 60):
        u = guess + timedelta(minutes=off)
        if u.astimezone(SYDNEY).replace(tzinfo=None) == naive and u not in out:
            out.append(u)
    return sorted(out)


def oracle_at(now: datetime, hh: int, mm: int) -> tuple[str, datetime | None]:
    """('scheduled', due) | ('needs_choice', None) | ('denied', None) for "at hh:mm" asked at now (UTC). The spec: the next occurrence within
    24 h; a time that is now, or skipped or doubled by a daylight-saving change (today, still ahead, or on the day it falls), is asked back."""
    local = now.astimezone(SYDNEY)
    today = local.date()
    wall_later = (hh, mm) > (local.hour, local.minute)
    t_inst = _instants(today, hh, mm)
    if (len(t_inst) == 2 and t_inst[-1] > now) or (len(t_inst) == 0 and wall_later):
        return 'needs_choice', None
    if (hh, mm) == (local.hour, local.minute):
        return 'needs_choice', None
    day = today if wall_later else today + timedelta(days=1)
    inst = _instants(day, hh, mm)
    if len(inst) != 1:
        return 'needs_choice', None
    due = inst[0]
    secs = (due - now).total_seconds()
    if secs <= 0 or secs > 86400:
        return 'denied', None
    return 'scheduled', due


def label_suffix(due: datetime, now: datetime) -> str:
    d, n = due.astimezone(SYDNEY), now.astimezone(SYDNEY)
    days = (d.date() - n.date()).days
    clock = f"{d.hour % 12 or 12}:{d.minute:02d} {'am' if d.hour < 12 else 'pm'}"
    return clock + ('' if days <= 0 else ' tomorrow' if days == 1 else f" on {d.strftime('%A')}")


# DST edges in Sydney: 2026-10-04 02:00 AEST -> 03:00 AEDT; 2027-04-04 03:00 AEDT -> 02:00 AEST.
EDGE_DAYS = [datetime(2026, 10, 3), datetime(2026, 10, 4), datetime(2027, 4, 3), datetime(2027, 4, 4), datetime(2026, 10, 18), datetime(2027, 1, 1)]


def rand_now(rng: random.Random) -> datetime:
    d = rng.choice(EDGE_DAYS)
    if rng.random() < 0.5:
        h = rng.choice([0, 1, 2, 3, 4, 23, 22])          # around the change hours
    else:
        h = rng.randrange(24)
    naive = datetime(d.year, d.month, d.day, h, rng.randrange(60))
    u = naive.replace(tzinfo=SYDNEY).astimezone(timezone.utc)
    return u if u.astimezone(SYDNEY).replace(tzinfo=None) == naive else u + timedelta(hours=1)   # a skipped wall time: take the next real one


SPOKEN = [('at {h}', 'bare'), ('at {h} am', 'am'), ('at {h} pm', 'pm'), ('at {h}:{m:02d}', 'bare'), ('at {h}:{m:02d} pm', 'pm'), ('at {h}.{m:02d} am', 'am'),
          ('at {h}:{m:02d}am', 'am'), ('at midnight', 'midnight'), ('at noon', 'noon'), ('at {H:02d}:{m:02d}', '24h')]


def spoken_hhmm(form: str, h: int, m: int, now: datetime) -> tuple[int, int]:
    """The independent reading of a spoken time: am/pm literal; a bare hour 1-12 is its next occurrence (h or h+12) by the wall clock."""
    local = now.astimezone(SYDNEY)
    if form == 'midnight':
        return 0, 0
    if form == 'noon':
        return 12, 0
    if form == '24h' and (h == 0 or h > 12):
        return h, m
    if form == '24h' and h < 10:
        return h, m                                        # zero-padded ("04:00"): a 24-hour time, never flipped to pm
    if form in ('am', 'pm'):
        return (h % 12) + (12 if form == 'pm' else 0), m
    for c in sorted({h % 12, h % 12 + 12}):
        if c * 60 + m > local.hour * 60 + local.minute:
            return c, m
    return h % 12, m


class Timers(unittest.TestCase):
    def setUp(self):
        if not HAVE_TZ:
            self.skipTest('needs tzdata for Australia/Sydney')

    def check_schedule(self, h: FakeHouse, args: dict, text: str, want: tuple[str, datetime | None]) -> str | None:
        r = h.call('atlas_schedule', args, user_text=text)
        if want[0] == 'scheduled':
            if r['status'] != 'scheduled':
                return f"{r['status']} ({r.get('reason')}), want scheduled at {want[1].astimezone(SYDNEY):%a %H:%M %Z}"
            t = next(x for x in h.coord.data['tasks'] if x['id'] == r['task'])
            if datetime.fromisoformat(t['due_at']) != want[1]:
                return f"due {datetime.fromisoformat(t['due_at']).astimezone(SYDNEY):%a %H:%M %Z}, want {want[1].astimezone(SYDNEY):%a %H:%M %Z}"
            if not r['label'].endswith(label_suffix(want[1], h.clock)):
                return f"label {r['label']!r}, want ... {label_suffix(want[1], h.clock)!r}"
            return None
        if r['status'] != want[0] or h.coord.data['tasks']:
            return f"{r['status']} ({r.get('reason')}), want {want[0]}"
        return None

    def test_absolute_times_against_the_oracle(self):
        rng = random.Random(SEED + 3)
        n, bad = 0, []
        for _ in range(700):
            now = rand_now(rng)
            if rng.random() < 0.4:                     # the change hours, and the minute of now itself, more often
                hh, mm = rng.choice([2, 2, 3, 1]), rng.choice([0, 15, 30, 59])
            elif rng.random() < 0.1:
                loc = now.astimezone(SYDNEY)
                hh, mm = loc.hour, loc.minute
            else:
                hh, mm = rng.randrange(24), rng.randrange(60)
            h = house(start=now)
            want = oracle_at(now, hh, mm)
            n += 1
            err = self.check_schedule(h, {'target_handle': 'office_lights', 'operation': 'on', 'at_time': f'{hh:02d}:{mm:02d}'}, 'office light on later', want)
            if err:
                bad.append(f"at {hh:02d}:{mm:02d} asked {now.astimezone(SYDNEY):%a %d %b %H:%M %Z}: {err}")
        record('timers: absolute', n, bad)
        report(self, 'timers: absolute', bad)

    def test_spoken_times_through_the_fast_path(self):
        rng = random.Random(SEED + 4)
        n, bad = 0, []
        for _ in range(450):
            now = rand_now(rng)
            tpl, form = rng.choice(SPOKEN)
            hr = rng.randrange(1, 13)
            mi = rng.choice([0, 5, 15, 30, 45, 59])
            H = rng.randrange(24)
            spoken = tpl.format(h=hr, m=mi, H=H)
            text = rng.choice(['office lights on {w}', 'turn the office lights off {w}', 'turn off the attic lamp {w}', '{W}, switch on the deck lights'])
            text = text.replace('{W}', cap(spoken)).replace('{w}', spoken)
            h = house(start=now)
            args = parse_timer(text, h.coord.handles, now.astimezone(SYDNEY))
            n += 1
            mm_ = mi if '{m' in tpl else 0
            hh, mm = spoken_hhmm(form, H if form == '24h' else hr, mm_, now)
            if args is None:
                bad.append(f'{text!r}: the fast path did not parse it')
                continue
            if args.get('at_time') != f'{hh:02d}:{mm:02d}':
                bad.append(f"{text!r} at {now.astimezone(SYDNEY):%H:%M}: at_time {args.get('at_time')}, want {hh:02d}:{mm:02d}")
                continue
            err = self.check_schedule(h, args, text, oracle_at(now, hh, mm))
            if err:
                bad.append(f"{text!r} asked {now.astimezone(SYDNEY):%a %d %b %H:%M %Z}: {err}")
        record('timers: spoken', n, bad)
        report(self, 'timers: spoken', bad)

    def test_relative_times_cap_and_firing(self):
        rng = random.Random(SEED + 5)
        n, bad = 0, []
        words = [('in {n} minutes', 1), ('in {n} mins', 1), ('in {k} hours', 60), ('in an hour and a half', None), ('in half an hour', None)]
        for _ in range(260):
            now = rand_now(rng)
            h = house(start=now)
            w, mult = rng.choice(words)
            if mult == 1:
                mins = rng.choice([1, 2, 10, 59, 60, 61, 119, 180, 1439, 1440, rng.randrange(1, 1441)])
                spoken = w.format(n=mins)
            elif mult == 60:
                k = rng.randrange(1, 25)
                mins, spoken = k * 60, w.format(k=k)
            else:
                mins, spoken = (90, w) if 'and a half' in w else (30, w)
            text = f'office lights on {spoken}'
            args = parse_timer(text, h.coord.handles, now.astimezone(SYDNEY))
            n += 1
            if args != {'target_handle': 'office_lights', 'operation': 'on', 'in_minutes': mins}:
                bad.append(f'{text!r}: parsed {args}')
                continue
            due = now + timedelta(minutes=mins)
            err = self.check_schedule(h, args, text, ('scheduled', due))
            if err:
                bad.append(f'{text!r} asked {now.astimezone(SYDNEY):%a %d %b %H:%M %Z}: {err}')
                continue
            h.advance(seconds=mins * 60 - 1)                  # not yet
            if h.tick() or h.calls:
                bad.append(f'{text!r}: ran early')
                continue
            if rng.random() < 0.3:
                h.set('light.office_ceiling', 'on')          # changed by hand meanwhile: a light timer still runs, skipping what is already on
            h.advance(seconds=1)
            out = h.tick()
            if [x['status'] for x in out] not in (['done'], ['skipped_already']) or h.state('light.office_ceiling')['state'] != 'on':
                bad.append(f'{text!r}: at the due time got {out}')
        # the cap: beyond 24 h is refused by the schema (in_minutes) and by _due (at_time)
        for mins in (1441, 1500, 10000):
            h = house()
            n += 1
            r = h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'on', 'in_minutes': mins}, user_text='office lights on later')
            if r['status'] != 'denied' or h.coord.data['tasks']:
                bad.append(f'in_minutes {mins}: {r["status"]}')
        for text in ('office lights on in 25 hours', 'office lights on in 1441 minutes', 'office lights on in 2000 minutes'):
            n += 1
            if parse_timer(text, house().coord.handles, datetime(2026, 10, 18, 19, 30, tzinfo=SYDNEY)) is not None:
                bad.append(f'{text!r}: the fast path accepted more than 24 h')
        record('timers: relative', n, bad)
        report(self, 'timers: relative', bad)

    def test_list_cancel_and_restart(self):
        rng = random.Random(SEED + 6)
        n, bad = 0, []
        handles = ['office_lights', 'attic_lamp', 'deck_lights', 'entry_lights']
        for _ in range(120):
            h = house(start=rand_now(rng))
            k = rng.randrange(1, 4)
            mine = []
            for i in range(k):
                r = h.call('atlas_schedule', {'target_handle': handles[i], 'operation': 'on', 'in_minutes': rng.randrange(5, 600)}, user_text=f'{handles[i]} on later',
                           conversation_id='A')
                mine.append(r['task'])
            other = h.call('atlas_schedule', {'target_handle': 'galley_lights', 'operation': 'on', 'in_minutes': 30}, user_text='galley lights on later',
                           conversation_id='B')
            n += 1
            lst = h.call('atlas_scheduled', {}, user_text="what's scheduled?", conversation_id='A')
            if lst['status'] != 'scheduled_list' or len(lst['tasks']) != k + 1:
                bad.append(f'list of {k + 1}: {lst}')
                continue
            c = h.call('atlas_cancel', {}, user_text='cancel that', conversation_id='A')
            want = 'cancelled' if k == 1 else 'needs_choice'
            if c['status'] != want or (want == 'cancelled' and c['task'] != mine[0]):
                bad.append(f'cancel with {k} here: {c["status"]}, want {want}')
                continue
            if k > 1:
                pick = rng.choice(mine)
                c = h.call('atlas_cancel', {'task': pick}, user_text='cancel that one', conversation_id='A')
                if c['status'] != 'cancelled':
                    bad.append(f'cancel by code: {c["status"]}')
                    continue
            left = len(h.call('atlas_scheduled', {}, user_text="what's scheduled?", conversation_id='A')['tasks'])
            if left != k:
                bad.append(f'after one cancel {left} left, want {k}')
                continue
            if h.call('atlas_cancel', {}, user_text='cancel that', conversation_id='C')['status'] == 'cancelled':
                bad.append('a conversation with no timer cancelled another one')
                continue
            h.restart()                                       # waiting timers are cancelled with a notice; nothing is replayed
            states = {t['id']: t['state'] for t in h.coord.data['tasks']}
            if any(s == 'pending' for s in states.values()) or not any(nn['task'] == other['task'] for nn in h.coord.notices):
                bad.append(f'after restart: {states}, notices {h.coord.notices}')
                continue
            h.advance(hours=24)
            if h.tick() or h.calls:
                bad.append('a cancelled timer ran')
        record('timers: list/cancel/restart', n, bad)
        report(self, 'timers: list/cancel/restart', bad)


# =============================================================== over-reach ===============================================================
ROOMS = {'office': 'office light', 'attic': 'attic lamp', 'family room': 'family room lamp', 'galley': 'galley lights', 'sunroom': 'sunroom lights',
         'carport': 'carport lights', 'deck': 'deck lights', 'entry': 'entry lights', 'corridor': 'corridor light', 'workshop': 'workshop bench light',
         'utility': 'utility light', 'bedroom south': 'bedroom south lamp'}
FLOORS = {'upstairs_lights': ['upstairs', 'first floor'], 'ground_floor_lights': ['downstairs', 'ground floor'], 'outside_lights': ['outside', 'outdoor']}
ROOM_TEXT = ['turn off the {x}', '{x} off please', 'switch the {x} off', 'turn off all the lights in my {r}', 'all lights off in the {r} please',
             'every light in my {r} off', 'turn off all the lights in {r}', 'turn the {r} lights off, all of them']
OTHER_FLOOR_TEXT = ['turn off all the lights {f}', 'all the lights {f} off', 'switch every light off {f}', 'turn off everything {f}']


class OverReach(unittest.TestCase):
    def test_floor_groups_need_their_own_scope(self):
        rng = random.Random(SEED + 7)
        cases = []
        for _ in range(260):
            handle = rng.choice(list(FLOORS))
            if rng.random() < 0.6:
                r = rng.choice(list(ROOMS))
                cases.append({'handle': handle, 'tpl': rng.choice(ROOM_TEXT), 'r': r, 'f': None, 'tool': rng.choice(['atlas_lights', 'atlas_schedule'])})
            else:
                f = rng.choice([w for k, ws in FLOORS.items() if k != handle for w in ws])
                cases.append({'handle': handle, 'tpl': rng.choice(OTHER_FLOOR_TEXT), 'r': None, 'f': f, 'tool': rng.choice(['atlas_lights', 'atlas_schedule'])})

        def text(c):
            return c['tpl'].format(r=c['r'], x=ROOMS.get(c['r'], ''), f=c['f'])

        def fails(c):
            args = {'target_handle': c['handle'], 'operation': 'off'} | ({'in_minutes': 10} if c['tool'] == 'atlas_schedule' else {})
            h = house()
            for e in h.targets['handles'][c['handle']]['entity_ids']:
                h.set(e, 'on')
            res = h.call(c['tool'], args, user_text=text(c))
            return None if res['status'] == 'needs_choice' and not h.calls and not h.coord.data['tasks'] else res['status']

        def steps(c):
            yield {**c, 'tool': 'atlas_lights'}
            if c['r'] is not None:
                yield {**c, 'r': 'office'}
            if c['f'] is not None:
                yield {**c, 'f': 'upstairs' if c['handle'] != 'upstairs_lights' else 'downstairs'}
        bad = []
        for c in cases:
            if fails(c):
                m = shrink(c, [steps], fails)
                bad.append(f"{m['tool']} {m['handle']} ran for {text(m)!r} ({fails(m)})")
        bad = sorted(set(bad))
        record('over-reach: floors', len(cases), bad)
        report(self, 'over-reach: floors', bad)

    def test_control_scope_named_runs(self):
        rng = random.Random(SEED + 8)
        n, bad = 0, []
        for _ in range(60):
            handle = rng.choice(list(FLOORS))
            f = rng.choice(FLOORS[handle])
            text = rng.choice(['turn off the {f} lights', 'all the lights {f} off', 'turn off everything {f}', 'switch off all the lights', '{f} lights off']).format(f=f)
            h = house()
            for e in h.targets['handles'][handle]['entity_ids']:
                h.set(e, 'on')
            n += 1
            r = h.call('atlas_lights', {'target_handle': handle, 'operation': 'off'}, user_text=text)
            if r['status'] != 'done':
                bad.append(f'{handle} refused for {text!r}: {r["status"]}')
        record('over-reach: controls', n, sorted(set(bad)))
        report(self, 'over-reach: controls', sorted(set(bad)))

    def test_fast_path_similar_names(self):
        """The fast path picks exactly the handle named (singular or plural), never a bigger group or a similar name."""
        now = datetime(2026, 10, 18, 19, 30, tzinfo=SYDNEY)
        hs = house().coord.handles
        want = {'attic lamp': 'attic_lamp', 'attic lamps': 'attic_lamp', 'attic light': 'attic_lights', 'attic lights': 'attic_lights',
                'family room lamp': 'family_room_lamp', 'family room lights': 'family_room_lights', 'office light': 'office_lights',
                'office ceiling': 'office_ceiling', 'upstairs lights': 'upstairs_lights', 'downstairs lights': 'ground_floor_lights',
                'outside lights': 'outside_lights', 'deck lights': 'deck_lights', 'deck light': 'deck_lights', 'flood lamp': 'flood_lamp',
                'entry downlight 1': 'entry_downlight_1', 'carport lights': 'carport_lights', 'galley pendant': 'galley_pendant'}
        none = ['attic', 'the house lights', 'all lights', 'upstairs lamp', 'office lamps please and the attic', 'garage lights', 'entry downlight',
                'family room', 'lights', 'carport ceiling']
        n, bad = 0, []
        for name, h in want.items():
            for tpl in ('turn the {n} off in 10 minutes', '{n} on at 7 pm', 'switch off the {n} in 5 mins', 'In 20 minutes, turn the {n} on'):
                n += 1
                a = parse_timer(tpl.format(n=name), hs, now)
                if not a or a['target_handle'] != h:
                    bad.append(f"{tpl.format(n=name)!r}: {a and a['target_handle']}, want {h}")
        for name in none:
            for tpl in ('turn the {n} off in 10 minutes', '{n} on at 7 pm'):
                n += 1
                a = parse_timer(tpl.format(n=name), hs, now)
                if a is not None:
                    bad.append(f"{tpl.format(n=name)!r}: picked {a['target_handle']}, want the model to ask")
        record('over-reach: fast path names', n, bad)
        report(self, 'over-reach: fast path names', bad)


# MINOR phrasing gaps (not generated: a fixed list of less common shapes, each claiming an action with no tool result at all)
MINOR_SHAPES = ["I've lit the lamp.", "I've drawn the blinds.", "I've pulled down the office blind.", "I've rolled the blind down.",
                "I've toggled the office light.", "I've cut the lights.", "I've dropped the blind.", "The office blind is now down.",
                "The blind is closing now.", "The office light's off now.", "The blind's closed now.", "I'm cancelling the timer.",
                "I've run the Galley Cooking scene.", "Galley Cooking scene running.", "The office lights are now switched off."]


class MinorPhrasings(unittest.TestCase):
    def test_less_common_claims_are_caught(self):
        bad = [r for r in MINOR_SHAPES if not guard_reply(r, [])[1]]
        record('claim guard: minor shapes', len(MINOR_SHAPES), [f'{r!r} with []: unbacked claim passed' for r in bad])
        report(self, 'claim guard: minor shapes', [f'{r!r}' for r in bad])

    def test_minor_never_words_brands_and_units(self):
        words = ['the Sonnen', 'the Victron', 'the Redback', 'the Selectronic', 'the Growatt', 'Amber Electric', 'the Yale', 'the Nuki', 'set export to 5 kW']
        bad = []
        for w in words:
            h = house()
            r = h.call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'on'}, user_text=f'turn on the office light and check {w}')
            if r.get('reason') != 'never_list':
                bad.append(f'turn on the office light and check {w!r} -> {r["status"]}')
        record('never-list: minor words', len(words), bad)
        report(self, 'never-list: minor words', bad)


class Total(unittest.TestCase):
    def test_zz_at_least_2000_cases(self):
        if len(COUNTS) < 10:
            self.skipTest('run the whole module for the total')
        self.assertGreaterEqual(sum(COUNTS.values()), 2000, COUNTS)


if __name__ == '__main__':
    if '--report' in sys.argv:
        sys.argv.remove('--report')
        prog = unittest.main(exit=False, verbosity=0)
        print('\nCASES', json.dumps(COUNTS, indent=1), 'total', sum(COUNTS.values()))
        for fam, fs in FAILURES.items():
            print(f'\n== {fam}: {len(fs)} minimal failing case(s)')
            for f in fs:
                print('  ', f)
    else:
        unittest.main()
