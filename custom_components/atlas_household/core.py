"""Atlas household coordinator: the pure-Python core (directive Lead 20261018-0142; the owner: "Yes to the commands proposal, with timers in v1.").

No Home Assistant import. The same code runs inside the integration (with a backend that calls HA) and in the recording fake (fake.py, which
sends nothing anywhere), so the fake returns exactly the coordinator's real result shapes.

Rules enforced in code, not left to the model (Codex 40 case ids in brackets):
  - the model names HANDLES from the allowed-target map; it never supplies an entity id, service name or consent flag [A027, A050];
  - unknown fields and values are rejected; disabled handles are not offered and are denied (media until each inverse is proven; AC is not a
    v1 tool) [A020-A023]; only a FROZEN map can be installed in HA (installable()) [A051];
  - a turn whose words touch the never-list (locks, doors, alarms, gates, battery, inverter, export, tariff...) is denied whole, so a mixed
    request is never partly done [A025, A026, A036];
  - skip-if-already from a fresh read; unknown or unavailable is never "already", and a partial "already" says what couldn't be checked [A002, A003];
  - do, then read back: "done" only when every entity read back as asked; otherwise "not_verified" or "failed" [A028, A029];
  - scenes run only with reviewed members and expected states (state, brightness, colour temperature, hue/saturation, effect), frozen into the
    map; an unreviewed scene is neither offered nor run [A012, A014];
  - blinds (R2) need a yes each time: the first call returns a preview question; atlas_confirm succeeds only if Atlas's last reply asked THAT
    question, the person's next turn is a plain yes, within 60 s, same conversation, and nothing moved since the preview. One open question per
    conversation: a new one replaces the old [A015-A017]; unknown or moving position: refused [A018];
  - every action gets a receipt with a before-image (including colour); undo restores it for 10 minutes unless the device changed since (any
    on/off change, even back to the same state, or a state that differs beyond the read-back tolerances; a dim-and-back that never
    switches the light is not seen, because HA keeps last_changed for attribute changes) or HA restarted since [A030-A032]; undoing a blind needs a yes again; one action per undo [A033];
  - a 30-day action log; a request id seen before in the same conversation returns the same result [A040];
  - timers (directive 20261018-1151 + am. 1): light and scene timers run at the due time even if the light was changed meanwhile (already-right
    lights skipped); a blind timer is re-checked and cancelled with a notice if the blind changed. A durable queue, up to 24 hours ahead and
    10 pending, due times kept in UTC [A034]; they switch lights on/off, run
    reviewed scenes
    or move blinds (a blind's yes is given when it is set); missed while HA was down: cancelled and reported, never run late [A041]; still to
    come after a restart: cancelled by default (restart_policy 'cancel_pending'); kept and re-checked against the device once HA has started
    only if the frozen map sets restart_policy 'keep_if_unchanged' (the owner's choice) [A042]; more than 30 s late, or the wall clock disagreeing
    with the monotonic clock: cancelled [A047]; the target changed by hand since it was set: cancelled; the map or the clock changed: stopped for review (needs_review) [A045-A047];
    mid-dispatch at a crash: outcome_unknown, never replayed [A043]; cancel and dispatch share a lock [A044];
  - the journal must be written before anything is sent; if it fails after a send, the coordinator stops acting until restart [A048];
  - disabling or reloading the integration cancels every pending timer [A049].
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

SCHEMA_VERSION = 1
LIMITS = {'undo_seconds': 600, 'confirmation_seconds': 60, 'maximum_delay_seconds': 86400, 'step_percent': 20, 'maximum_pending_tasks': 10,
          'maximum_uptime_lateness_seconds': 30, 'audit_retention_days': 30, 'media_volume_cap_percent': 40,
          'readback_timeout_seconds': 8, 'blind_readback_timeout_seconds': 45, 'brightness_tolerance_percent': 2,
          'position_tolerance_percent': 3, 'kelvin_tolerance': 100, 'hue_tolerance': 4, 'saturation_tolerance': 4,
          'request_memory_seconds': 600, 'clock_disagreement_seconds': 60}
ALLOWED_DOMAINS = {'light': 'light', 'scene': 'scene', 'blind': 'cover', 'media': 'media_player'}
EXPECT_KEYS = {'state', 'brightness_percent', 'color_temp_kelvin', 'hs_color', 'effect'}
# Defence in depth: whatever the map says, these never become targets (energy, locks, alarms, door openers, gates).
FORBIDDEN = re.compile(r'(battery|inverter|export|sungrow|tariff|solar|grid|energy|powerwall|lock|alarm|garage_door|front_door|back_door|side_door|'
                       r'roller_door|door_opener|opener|gate)', re.I)
# A blind is accepted only if the map lists it in reviewed_covers with the device class it was reviewed with, and at run time it still
# reports that class. Names alone never make a cover safe (Codex 43 H2): a garage door, gate or window opener is refused.
ALLOWED_COVER_CLASSES = {'shade', 'blind', 'curtain', 'awning', 'shutter'}
# ...and a cover NAMED like a door is refused whatever class it was reviewed with: roller garage doors often report "shutter"
# [cloud review 1, M4]. "..._door_blind" and "..._roller_blind" stay allowed.
COVER_FORBIDDEN = re.compile(r'(?<![a-z])(garages?|carports?|driveways?|sheds?|gates?|doors?(?!_?blinds?))', re.I)   # not bare "roller": a roller blind is a blind (the Somfy li_ion_roller); a roller door has "door"
# Never-list subjects in the person's own words: the whole turn is refused, so nothing is done partly.
NEVER_WORDS = re.compile(r"\b(un ?lock\w*|lock(s|ed|ing)?|alarm\w*|(garage|front|back|side|roller)[- ]?doors?|door ?locks?|(door )?openers?|"
                         r"(open|close|shut|lift|raise|lower|unlatch|release)\s+(the\s+|my\s+|our\s+|a\s+)?([\w-]+\s+){0,2}?(garages?|doors?)\b"
                         r"(?![\s-]*(lights?|lamps?|blinds?|downlights?|spotlights?))|"
                         r"gates?|batter(y|ies)|inverter\w*|export\w*|tariff\w*|reserve|discharg\w*|sungrow|power ?wall|energy|solar|grid|self[- ]?use|"
                         r"feed[- ]?in|backup power|pv|photovoltaic|the panels|disarm\w*|arm\w*\s+(the\s+|my\s+|our\s+)?(house|home|system|security|alarm)|"
                         r"secure (the|my|our) (house|home|place)|away mode|security(?!\s+lights?)|garage\s+(up|down|open|closed)|pop the garage|"
                         r"(the\s+)?rollers?(?![\s-]*blinds?)|(house|home) to away|arm\w*\s+(everything|(it|them) all)|(ev|car)\s+charg\w*|wallbox|ev|"
                         r"charg\w*\s+(the\s+|my\s+)?(car|ev)|plug in the (car|ev)|"
                         # cloud review 1, M2: lock hardware, securing, the grid and tariff in other words, energy brands, door strikes
                         r"deadbolt\w*|latch\w*|padlock\w*|keypad\w*|sirens?|intruder\w*|(house|home|place)\s+(is\s+)?secure|garages|"
                         r"electricity|off[- ]?peak|peak\s+(rate|hours?|time|tariff|pricing)|cheap\s+rate|kwh|kilowatt\w*|mains|"
                         r"power\s+(bill|usage|use|plan|rate|price|company|draw)|tesla|fronius|enphase|solaredge|goodwe|zappi|buzz\s+(\w+\s+){0,2}in)\b",
                         re.I)   # whole-turn refusal [Codex 43 H2, R12-05, R13-07, cloud review 1]
AFFIRMATIVE = re.compile(r"^\s*(yes|yep|yeah|yup|ok|okay|sure|please do|do it|go ahead|confirm(ed)?|yes please|correct)\b[\s.!,]*(please)?[\s.!]*$", re.I)
STATUSES = ('done', 'skipped_already', 'needs_confirmation', 'denied', 'scheduled', 'cancelled', 'undone', 'not_verified', 'failed',
            'needs_choice', 'scheduled_list')
ACTING = {'atlas_lights', 'atlas_scene', 'atlas_blind', 'atlas_media', 'atlas_confirm', 'atlas_schedule', 'atlas_undo'}
# A floor-wide or whole-outside group (a multi-light handle with a floor, or with no area) is used only when the person's words name that scope
# or all the lights; otherwise ask. A model that picks "ground_floor_lights" for "the family room lamp" would switch 14 lights [cloud review 1, M11].
SCOPE_SYNONYMS = {'ground': ('downstairs', 'ground floor'), 'upstairs': ('first floor', 'top floor', 'up stairs'), 'outside': ('outdoor', 'outdoors', 'exterior')}
ALL_LIGHTS = re.compile(r"\b(all(\s+of)?\s+(the\s+)?lights|every\s+light|everywhere|whole\s+(house|home|place))\b(?!\s+(in|on|at)\s+the\b)", re.I)
NEVER_SCOPE = ACTING | {'atlas_cancel'}      # a cancel changes what will happen, so it is refused in a never-list turn too [cloud review 1, M3]


class Backend(Protocol):
    """What the core needs from the house. The HA backend calls hass; the fake records and changes a dict."""
    async def get_state(self, entity_id: str) -> dict | None: ...   # {'entity_id', 'state', 'attributes', 'last_changed'} or None
    async def call(self, domain: str, service: str, entity_ids: list[str], data: dict) -> None: ...
    async def wait_for(self, entity_id: str, predicate, timeout: float) -> dict | None: ...   # the state that matched, or the last seen


class Store(Protocol):
    async def load(self) -> dict | None: ...
    async def save(self, data: dict) -> None: ...


class JournalError(Exception):
    def __init__(self, after_send: bool, cause: Exception) -> None:
        super().__init__(f'journal write failed ({"after" if after_send else "before"} send): {type(cause).__name__}: {cause}')
        self.after_send = after_send


# ---------- the claim guard (the lead project, within directive 0142: sealed C0d had 3 false "done" with no tool call) ----------
_APOS = str.maketrans({'\u2019': "'", '\u2018': "'", '\u02bc': "'"})          # curly apostrophes [R12-04]
# A negation vetoes a claim only when it sits just before the claim in the same clause ("I have not turned...", "Nothing has been
# changed", "No timer has been set") [R12-02, R13-03].
_NEG_BEFORE = re.compile(r"\b(can't|cannot|can not|couldn't|could not|didn't|did not|haven't|have not|hasn't|has not|won't|will not|wasn't|weren't|isn't|"
                         r"aren't|not(?!\s+to\s+worry)|never|unable to|no longer|nothing|no(?!\s+(?:problem|worries|trouble|need)))\b(\s+[\w']+){0,3}\s*$", re.I)      # same clause, no punctuation between
_NONE_AFTER = re.compile(r"^\s+(nothing|none|no\b)", re.I)                                    # "I set nothing."
_ADV = r"(?:(?:also|now|just|then|already|successfully|quickly|not only|gone ahead and|went ahead and|go ahead and|\w+ly)\s+){0,3}"
_DID = (r"(turned|switched|set(?!\s+(?:up\s+)?(?:a|an|the|your)\s+(?:timer|reminder))|opened|closed|dimmed|brightened|raised|lowered|activated|enabled|"
        r"disabled|started|stopped(?!\s+(?:making|doing|sending|changing|trying))|cranked|put|changed|adjusted|ran|killed|shut|paused|muted|unmuted|played|resumed|skipped|applied|triggered|recalled|restored|moved|"
        r"flicked|flipped|popped|powered)")
_PP = r"(turned|switched|set|opened|closed|dimmed|brightened|raised|lowered|activated|enabled|changed|adjusted|paused|muted|started|stopped)"
_DO = r"(turn|switch|open|close|dim|brighten|set|run|put|start|stop|activate|lower|raise|pause|mute|play)"
_ING = r"(turning|switching|opening|closing|dimming|brightening|setting|activating|starting|stopping|running|putting|lowering|raising|pausing|muting)"
_THING = r"(lights?|lamps?|blinds?|downlights?|spotlights?|scene)"
_OK = r"(?:(?:ok(?:ay)?|sure(?: thing)?|right|alright|all right|great|no problem|got it|on it|cool|yes|yep)\W+)*"
_NOT_SUBJECT = r"(?!(?:I|we|you|it|they|he|she|there)\b)"                                    # "I sent the lights on" is not verbless
_WHEN = (r"\b(?:at\s+\d|at\s+(?:noon|midnight)|in\s+(?:\d+|an?|one|two|three|four|five|six|seven|eight|nine|ten|fifteen|twenty|thirty|forty|"
         r"forty-five|fifty|sixty|half)\b|tomorrow|tonight|this (?:evening|afternoon|morning)|later\b|at that time)")   # [RT106; B16-05: not "automatically", which describes automations]
_WILL = r"(?:I'll|I will|I'm going to|(?:it|they|[\w ]{0,30}?\b(?:lights?|lamps?|blinds?|scene)) will)\s+" + _ADV + r"(?:" + _DO[1:-1] + r"|go|be turned|be switched)\b"
_SCHED_FUTURE = re.compile(r"\b" + _WILL + r".{0,60}" + _WHEN, re.I)          # "I'll dim the loft at 9 pm", "Your lights will switch off in 10 minutes"
_SCHED_FUTURE_FIRST = re.compile(_WHEN + r".{0,40}?\b" + _WILL, re.I)          # "In 10 minutes, the lights will turn off" [cloud review 1, m3]
# exclusions read the words right after the claim, up to a "so/because/as" (R14-04: not "...now so the room isn't too bright")
_FAILED_AFTER = re.compile(r"^(?:(?!\b(?:so|because|as|since)\b)[^,;]){0,50}?\b(didn't|did not|failed|isn't|is not|doesn't|does not|won't|can't|cannot|needs|"
                           r"wasn't|was not)\b", re.I)
_PAST_TIME = re.compile(r"^(?:(?!\b(?:so|because)\b)[^;]){0,60}?(\b(ago|yesterday|earlier|last night|since|this morning)\b|\bat \d{1,2}(:\d\d)?\s*(am|pm)\b)", re.I)
# (kind, future, pattern, exclude). A FUTURE claim (a promise or offer) is excused by a condition anywhere in its clause ("if you'd like",
# "once you say yes"); a past or present claim only by a condition governing it, just before it (R13-01).
_CLAIMS = [
    ('action', False, re.compile(r"\bI(?:'ve| have| had)?\s+" + _ADV + _DID + r"\b", re.I), None),
    ('action', False, re.compile(r"\bI did\s+" + _DO + r"\b", re.I), None),
    ('action', False, re.compile(r"\bI'm\s+" + _ADV + _ING + r"\b", re.I), None),
    ('action', False, re.compile(r"^\W*" + _OK + _ING + r"\b", re.I), _FAILED_AFTER),       # "Turning off the lights now." (not "Turning it off failed")
    ('action', False, re.compile(r"\b(is|are)\s+now\s+(on|off|open|closed|dimmed|brighter|dimmer|set|running|playing|paused|muted|active)\b", re.I), None),
    ('action', False, re.compile(r"\b(is|are|should be)\s+(on|off|open|closed)\s+now\b(?!\s+in\b)", re.I), None),   # not "on now in the study"
    ('action', False, re.compile(r"\b(has|have|had)\s+been\s+" + _PP + r"\b", re.I), None),
    ('action', False, re.compile(r"\b(was|were)\s+(just|now|successfully)\s+" + _PP + r"\b", re.I), None),   # not "were turned off at 9" (history)
    ('action', False, re.compile(r"\b(has|have)\s+gone\s+(off|out)\b|\b(just\s+)?went\s+(off|out)\b", re.I), _PAST_TIME),     # not "went off at 9 pm"
    # an acknowledgement ("Done!", "All set") claims that whatever was asked happened: a timer set or cancelled backs it too [cloud review 1, M7]
    ('ack', False, re.compile(r"^\W*" + _OK + r"(done|all done|all set|sorted|that's (done|sorted)|consider it done|you're all set|finished|there you go|"
                              r"here you (go|are)|taken care of)\b", re.I), None),
    ('ack', False, re.compile(r"\bI(?:'ve| have)?\s+taken care of (it|that|this)\b", re.I), None),
    ('action', False, re.compile(r"\bI(?:'ve| have)?\s+" + _ADV + r"got\s+(?:the\s+|your\s+|all\s+the\s+)?(?:[\w']+\s+){0,3}?" + _THING
                                 + r"\s+(?:on|off|open|closed|up|down)\b", re.I), None),       # "I've got the lights off" [m3]
    ('action', False, re.compile(r"\bshould\s+now\s+be\s+(on|off|open|closed)\b", re.I), None),  # "The lights should now be off" [m3]
    ('action', False, re.compile(r"^\W*(turned|switched)\s+(on|off)\b", re.I), None),          # "Turned on the light" (HA's own wording)
    ('action', False, re.compile(r"^\W*" + _OK + _NOT_SUBJECT + r"(the\s+)?([\w']+\s+){0,3}" + _THING + r"\s+(now\s+)?(on|off|open|closed|up|down)(\s+now)?\W*$",
                                 re.I), None),                                                  # "Lights off." (no verb)
    ('action', False, re.compile(r"^\W*" + _OK + _NOT_SUBJECT + r"(the\s+)?([\w']+\s+){0,3}" + _THING + r"\s+(dimmed|brightened|lowered|raised|opened|closed|"
                                 r"activated|set|turned (on|off)|switched (on|off))\b", re.I), _PAST_TIME),   # "Lights dimmed to 40%." (not a history answer)
    ('action', True, re.compile(r"\b(?:I'll|I will|I'm going to|let me)\s+" + _ADV + _DO + r"\b", re.I), None),     # "I'll turn off the lights now."
    # an offer stated, not asked ("I can, however, turn the lights off for you."): by voice it can sound done (C0d D01/D59, RT032)
    ('action', True, re.compile(r"\bI can(?:,?\s*however,?|\s+certainly|\s+definitely|\s+also)?\s+(turn|switch|set|open|close|dim|brighten|run|put|start|stop)\b"
                                r"[^?]*\bfor you\b[^?]*$", re.I), None),
    ('undone', False, re.compile(r"\b(I(?:'ve| have)?\s+" + _ADV + r"(undone|reverted)|I\s+" + _ADV + r"undid|put (it|them|that) back|that's (been )?(undone|reverted))\b"
                                 r"|^\W*(undone|reverted)\b", re.I), None),                     # [R12-11, R13-04]
    ('scheduled', False, re.compile(r"\b(timer(?:'s|\s+is|\s+has)?(?:\s+been)?\s+(?:now\s+)?set|I(?:'ve| have)?\s+" + _ADV
                                    + r"(scheduled|set (up )?(a|an|the|your) (timer|reminder)))\b", re.I), None),   # "Timer's set" [cloud review 1, M5]
    ('scheduled:future', True, _SCHED_FUTURE, None),                                            # "I'll dim the loft at 9 pm", "in five minutes"
    ('scheduled:future', True, _SCHED_FUTURE_FIRST, None),
    # "already" after a turn that changed something (done) is false unless the reply also says what changed (C0e E12) [see guard_reply]
    ('already', False, re.compile(r"\b(is|are|was|were)\s+(all\s+)?already\s+(on|off|open|closed|shut|set|at|dimmed|running|playing|paused)\b|"
                                  r"\balready\s+(on|off|open|closed|at full|at the lowest)\b|\bnothing (needed|to) (to )?(change|do)\b", re.I), None),
    ('cancelled', False, re.compile(r"\b(I(?:'ve| have)?\s+" + _ADV + r"(cancell?ed|removed|deleted|cleared|stopped) (the|that|your|those) timers?|"
                                    r"I(?:'ve| have)?\s+" + _ADV + r"cancell?ed\b|timer(?:'s| is| has)? (been )?cancell?ed|cancell?ed (the|that|your) timer)", re.I), None),
]
# What backs a claim: a same-turn atlas_ result of that kind. A timer list (scheduled_list) backs future-tense timer statements [R13-03], never
# "I've set a timer" / "Timer set" [cloud review 1, M6].
# A send that couldn't be confirmed backs an action claim only when the reply says so (a caveat), e.g. "...but one didn't report back" [R13-02].
_BACKED_BY = {'action': {'done', 'undone'}, 'ack': {'done', 'undone', 'scheduled', 'cancelled'}, 'undone': {'undone'}, 'scheduled': {'scheduled'},
              'scheduled:future': {'scheduled', 'scheduled_list'}, 'cancelled': {'cancelled'},
              'already': {'skipped_already'}}
# Which tools can back a claim, when the evidence names them ((tool, status) pairs from Coordinator.evidence_since): a claim about a blind
# needs a blind result, about a scene a scene result, about lights a lights or scene result; a timer claim a timer result [cloud review 1, M8].
# A bare status (no tool) backs as before.
_THINGS = {'blind': re.compile(r"\b(blinds?|curtains?|shades?|shutters?)\b", re.I), 'scene': re.compile(r"\bscenes?\b", re.I),
           'light': re.compile(r"\b(lights?|lamps?|downlights?|spotlights?)\b", re.I)}
_THING_TOOLS = {'blind': {'atlas_confirm', 'atlas_undo'}, 'scene': {'atlas_scene', 'atlas_undo'}, 'light': {'atlas_lights', 'atlas_scene', 'atlas_undo'}}
_KIND_TOOLS = {'scheduled': {'atlas_schedule', 'atlas_confirm'}, 'scheduled:future': {'atlas_schedule', 'atlas_confirm', 'atlas_scheduled'},
               'cancelled': {'atlas_cancel'}}
_TIMER_OBJECT = re.compile(r"^\s*(?:off\s+)?(?:[\w:']+\s+){0,4}?timers?\b", re.I)                # "I've turned off the (9 pm) timer"
_TIMER_STOP = re.compile(r"\b(stopped|turned off|switched off|killed|cleared|removed|deleted|cancell?ed)\b", re.I)
_LATER = re.compile(r"\bto\s+(?:turn|switch|go|come|be)\b.*" + _WHEN, re.I)                      # "I've set the lights to turn off at 9 pm"
_CAVEAT = re.compile(r"\b(couldn't|could not|can't|cannot|didn't|did not|unable to)\s+(confirm|verify|check|reach)|report(ed)? back|"
                     r"not (been )?(confirmed|verified)|didn't respond|no response", re.I)
_UNCONFIRMED_SEND = {'not_verified', 'failed_sent'}       # something WAS sent; a "failed" with nothing sent never backs a claim [R14-01]
# Anything sent this turn (by an atlas_ tool, or by another tool the underlying agent has: external_tool). Then "I haven't changed anything"
# would be untrue, so the head is "I can't confirm all of that." [R12-06, R13-02, R13-06]
_SENT = {'done', 'undone', 'scheduled', 'cancelled', 'not_verified', 'failed', 'failed_sent', 'tool_error', 'external_tool'}
_QUESTION = re.compile(r"^\W*(shall|should|would|do|does|did|can|could|may|might|want|will|is|are|what|which|when|where|how|who)\b[^?]*\?\W*$", re.I)
_COND = re.compile(r"\b(if you|if that|would you|do you want|want me|shall I|should I|"
                   r"(?:once|when|after|as soon as) you(?:'ve| have)?\s+(?:say|said|confirm|answer|reply|give|tell|agree|approve|okay|ok)|say yes|just confirm|"
                   r"confirm and|when confirmed)\b", re.I)                # not "when you go to bed" [cloud review 1, m3]
_AFTER_THAT = re.compile(r"\b(?:now that|since|after|as|because)\b(.*)$", re.I)                 # "Shall I ..., now that I've turned off the lights?"
_COND_BEFORE = re.compile(r"\b(if you|would you like me to|do you want me to|shall I|should I)\b(\s+[\w']+){0,3}\s*$", re.I)
_CLAUSE = re.compile(r"\s*;\s*|\s+[-–—]\s+|,?\s+(?=(?:but|although|though|whereas|yet)\s+\w)|,\s+(?=and\b)|\s+(?=and I\s)|"
                     r",\s+(?=(?:let me know|would you|would that|do you|should I|shall I|want me|is there|anything else|if you need|feel free|"
                     r"just (?:ask|say|let)|enjoy)\b)", re.I)
_LEAD = re.compile(r"^(but|however|although|though|yet|whereas|and)\b,?\s*", re.I)


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r'(?<=[.!?])\s+|\n+', (text or '').strip()) if s.strip()]


def _claims(clause: str) -> list[str]:
    kinds = []
    future_with_time = bool(_SCHED_FUTURE.search(clause) or _SCHED_FUTURE_FIRST.search(clause))
    for k, future, rx, exclude in _CLAIMS:
        for m in rx.finditer(clause):
            before = clause[:m.start()]
            if _NEG_BEFORE.search(before) or _NONE_AFTER.match(clause[m.end():]):
                continue
            if (future and _COND.search(clause)) or _COND_BEFORE.search(before) or (exclude is not None and exclude.search(clause[m.end():])):
                continue
            if k == 'action' and future_with_time and re.match(r"(?:I'll|I will|I'm going to|let me)\b", m.group(0), re.I):
                continue                       # a future action with a time is a timer claim, not a "done" claim
            if k == 'action' and _TIMER_OBJECT.match(clause[m.end():]):
                k = 'cancelled' if _TIMER_STOP.search(clause) else 'scheduled'     # "I've stopped the timer", "I've turned off the timer" [M7]
            elif k == 'action' and not future and _LATER.search(clause[m.end():]):
                k = 'scheduled'                # "I've set the office lights to turn off at 9 pm" is a timer claim [M7]
            kinds.append(k)
            break
    return kinds


def _backing(kind: str, clause: str, ev: list[tuple[str | None, str]]) -> set[str]:
    """The statuses that may back a claim of this kind in this clause: every result whose tool fits what the clause is about."""
    tools = _KIND_TOOLS.get(kind)
    things = [t for t, rx in _THINGS.items() if rx.search(clause)] if tools is None else []

    def fits(tool):
        if tool is None:
            return True
        if tools is not None:
            return tool in tools
        return all(tool in _THING_TOOLS[t] for t in things)
    if tools is None and len(things) > 1:          # "the lights are off and the blind is closed": every thing needs its own result
        return set.intersection(*[{st for tool, st in ev if tool is None or tool in _THING_TOOLS[t]} for t in things])
    return {st for tool, st in ev if fits(tool)}


def guard_reply(reply: str, statuses: list) -> tuple[str, list[str]]:
    """Deterministic claim guard. If Atlas's final reply claims an action (done, scheduled, cancelled, undone, past or present action wording,
    or an action promised for now) that no same-turn tool result backs, the claiming clauses are dropped and the reply starts
    "I haven't changed anything." only when nothing at all was sent this turn, else "I can't confirm all of that.", followed by the honest
    clauses. Checked per clause; questions ("Shall I...?") and conditional offers ("I'll close them once you say yes") claim nothing.
    Returns (reply, the unbacked claim kinds); an empty list means the reply passes through unchanged."""
    ev = [(None, x) if isinstance(x, str) else (x[0], x[1]) for x in statuses or []]     # bare statuses, or (tool, status) pairs [M8]
    have = {st for _, st in ev}
    text = re.sub(r"\bIve\b", "I've", (reply or '').translate(_APOS))
    sents = _sentences(text)
    caveat_at = {i for i, s in enumerate(sents) if _CAVEAT.search(s)} if have & _UNCONFIRMED_SEND else set()
    if 'done' in have and any('action' in _claims(c) for s in sents for c in _CLAUSE.split(s) if c and c.strip()):
        ev.append((None, 'skipped_already')); have.add('skipped_already')        # a partial change said as such ("turned off 5; 23 were already off") backs its already part [E12]
    keep, bad = [], []
    for n, s in enumerate(sents):
        # an honest "sent, but couldn't confirm" may say what was sent, with the caveat in the same or the next sentence
        ev_s = ev + [(tool, 'done') for tool, st in ev if st in _UNCONFIRMED_SEND] if (n in caveat_at or n + 1 in caveat_at) else ev
        if _QUESTION.match(s):
            # a question claims nothing, unless it states a claim as its premise ("..., now that I've turned off the lights?") [M5]
            tail = _AFTER_THAT.search(s)
            unbacked = [k for k in (_claims(tail.group(1)) if tail else []) if not (_BACKED_BY[k] & _backing(k, s, ev_s))]
            if unbacked:
                bad += [k.split(':')[0] for k in unbacked]
            else:
                keep.append(s)
            continue
        parts, dropped = [], False
        for c in [c for c in _CLAUSE.split(s) if c and c.strip()]:
            # "already" is only checked after a turn that changed something: with no result it is a state statement from the readings [E12]
            unbacked = [k.split(':')[0] for k in _claims(c) if not (_BACKED_BY[k] & _backing(k, c, ev_s))
                        and not (k == 'already' and 'done' not in {st for _, st in ev_s})]
            if unbacked:
                bad += unbacked
                dropped = True
            else:
                parts.append(c.strip())
        if not dropped:
            keep.append(s)
            continue
        t = _LEAD.sub('', ' '.join(p for p in parts if re.search(r'\w', _LEAD.sub('', p)))).strip()
        if re.search(r'\w', t):
            t = t[:1].upper() + t[1:]
            keep.append(t if t[-1:] in '.!?' else t + '.')
    if not bad:
        return reply, []
    head = "I can't confirm all of that." if have & _SENT else "I haven't changed anything."
    heads = {"i haven't changed anything.", "i can't confirm all of that."}
    keep = [k for k in keep if k.strip().lower() not in heads]          # never say the head twice (RT106's reply already began with it)
    return ' '.join([head] + keep).strip(), sorted(set(bad))


def installable(targets: dict) -> str | None:
    """None if this map may be loaded into Home Assistant: a frozen household map, or the test-only demo map. Drafts never install [A051]."""
    v = str(targets.get('version', ''))
    if targets.get('test_only') is True or v.startswith('frozen-'):
        return None
    return f'map version {v!r} is not frozen'


def _r(status: str, summary: str, **kw) -> dict:
    assert status in STATUSES, status
    out = {'status': status, 'summary': summary}
    out.update({k: v for k, v in kw.items() if v is not None})
    return out


def _deny(reason: str, summary: str, **kw) -> dict:
    return _r('denied', summary, reason=reason, **kw)


def _clock(t: datetime) -> str:
    return f"{t.hour % 12 or 12}:{t.minute:02d} {'am' if t.hour < 12 else 'pm'}"


def _when(due: datetime, now: datetime, tz) -> str:
    """'7:00 am' today, '7:00 am tomorrow', or '7:00 am on Monday' further out (DST nights can push a 24 h timer two days on) [R8-01, R9-03]."""
    d, n = due.astimezone(tz), now.astimezone(tz)
    days = (d.date() - n.date()).days
    return _clock(d) + ('' if days <= 0 else ' tomorrow' if days == 1 else f" on {d.strftime('%A')}")


def _words(s: str) -> str:
    return ' '.join(re.findall(r'[a-z0-9%]+', (s or '').lower()))


NO_EFFECT = (None, '', 'none', 'off', 'None', 'Off')


def _effect(v):
    """An active effect name, or None for absent / "none" / "off"."""
    return None if v in NO_EFFECT else v


def _snap(st: dict | None) -> dict | None:
    """The before-image kept for undo, and the facts used for 'already'. rev = HA's last_changed (a change revision)."""
    if st is None:
        return None
    a = st.get('attributes', {})
    dom = str(st.get('entity_id', '')).split('.')[0]
    out = {'state': st.get('state'), 'rev': st.get('last_changed')}
    if dom in ('light', ''):
        if a.get('brightness') is not None:
            out['brightness_percent'] = round(a['brightness'] / 2.55)
        for k in ('color_mode', 'color_temp_kelvin'):
            if a.get(k) is not None:
                out[k] = a[k]
        if _effect(a.get('effect')) is not None:
            out['effect'] = a['effect']
        if a.get('hs_color') is not None:
            out['hs_color'] = [round(float(x), 1) for x in a['hs_color']]
    if dom in ('cover', ''):
        if a.get('current_position') is not None:
            out['position_percent'] = a['current_position']
        elif dom == 'cover' and int(a.get('supported_features') or 0) & 4:
            out['position_unknown'] = True        # it can report a position but isn't: never guess from "open"
    return out


def _position(s: dict) -> int | None:
    if s.get('position_percent') is not None:
        return s['position_percent']
    if s.get('position_unknown'):
        return None
    return 100 if s['state'] == 'open' else 0 if s['state'] == 'closed' else None


def _light_match(want: dict):
    """A predicate: the light's state matches every field of want (state, and when on: brightness, colour temperature, hue/saturation, effect)."""
    def ok(st):
        if st is None:
            return False
        s = _snap(st)
        if s['state'] != want['state']:
            return False
        if want['state'] != 'on':
            return True
        if want.get('brightness_percent') is not None and (s.get('brightness_percent') is None or
                                                           abs(s['brightness_percent'] - want['brightness_percent']) > LIMITS['brightness_tolerance_percent']):
            return False
        if want.get('color_temp_kelvin') is not None and (s.get('color_temp_kelvin') is None or
                                                          abs(s['color_temp_kelvin'] - want['color_temp_kelvin']) > LIMITS['kelvin_tolerance']):
            return False
        if want.get('hs_color') is not None:
            hs = s.get('hs_color')
            if hs is None:
                return False
            dh = abs(hs[0] - want['hs_color'][0]) % 360
            if min(dh, 360 - dh) > LIMITS['hue_tolerance'] or abs(hs[1] - want['hs_color'][1]) > LIMITS['saturation_tolerance']:
                return False
        if 'effect' in want and _effect(s.get('effect')) != _effect(want['effect']):     # want None = no effect running
            return False
        return True
    return ok


def _light_restore(before: dict, now: dict | None = None) -> tuple[str, dict, dict]:
    """(service, data, want) that puts a light back to its before-image, colour and effect included (an effect started since is turned off)."""
    if before['state'] != 'on':
        return 'turn_off', {}, {'state': 'off'}
    data, want = {}, {'state': 'on'}
    if before.get('brightness_percent') is not None:
        data['brightness_pct'] = want['brightness_percent'] = max(1, before['brightness_percent'])   # 0% after rounding is still on: never off
    if before.get('color_mode') == 'color_temp' and before.get('color_temp_kelvin'):
        data['color_temp_kelvin'] = want['color_temp_kelvin'] = before['color_temp_kelvin']
    elif before.get('color_mode') in ('hs', 'xy', 'rgb', 'rgbw', 'rgbww') and before.get('hs_color'):
        data['hs_color'] = want['hs_color'] = before['hs_color']
    want['effect'] = _effect(before.get('effect'))                  # always checked, including "no effect"
    if want['effect'] is not None:
        data['effect'] = want['effect']                             # e.g. a Hue "candle" effect comes back
    elif _effect((now or {}).get('effect')) is not None:
        data['effect'] = 'off'                                      # a scene started one (e.g. prism): turn it off
    return 'turn_on', data, want


def _same(a: dict | None, b: dict | None) -> bool:
    """Two snapshots show the same device state (the change revision aside). HA moves last_changed only on on/off, so a hand dimming or
    colour change is caught here, not by the revision."""
    if a is None or b is None:
        return False
    keys = (set(a) | set(b)) - {'rev'}
    tol = {'brightness_percent': LIMITS['brightness_tolerance_percent'], 'color_temp_kelvin': LIMITS['kelvin_tolerance'],
           'position_percent': LIMITS['position_tolerance_percent']}
    for k in keys:
        x, y = a.get(k), b.get(k)
        if k in tol and x is not None and y is not None:
            if abs(x - y) > tol[k]:
                return False
        elif k == 'hs_color' and x is not None and y is not None:
            dh = abs(x[0] - y[0]) % 360
            if min(dh, 360 - dh) > LIMITS['hue_tolerance'] or abs(x[1] - y[1]) > LIMITS['saturation_tolerance']:
                return False
        elif x != y:
            return False
    return True   # same within the read-back tolerances (a light caught mid-fade isn't "changed by hand")


def _digest(t: dict) -> str:
    return hashlib.sha256(json.dumps(t, sort_keys=True).encode()).hexdigest()[:16]


def _utc(t: datetime) -> datetime:
    return t.astimezone(timezone.utc)


class Coordinator:
    def __init__(self, targets: dict, backend: Backend, store: Store, now, tz, mono=time.monotonic) -> None:
        self.backend, self.store, self.now, self.tz, self.mono = backend, store, now, tz, mono
        self.handles = self._check_targets(targets)
        self.reviewed_covers = dict(targets.get('reviewed_covers') or {})
        self.restart_policy = targets.get('restart_policy', 'cancel_pending')
        self.timer_blinds = targets.get('timer_blinds') is True
        self.replaced: dict[str, list[str]] = {}            # conversation -> questions replaced by a newer one (for an ambiguous yes)
        if self.restart_policy not in ('cancel_pending', 'keep_if_unchanged'):
            raise ValueError(f'unknown restart_policy {self.restart_policy!r}')
        self.data: dict = {'version': SCHEMA_VERSION, 'tasks': [], 'receipts': [], 'log': []}
        self.pending_confirmations: dict[str, dict] = {}     # not persisted: a restart drops them (fail closed)
        self.requests: dict[tuple, tuple[datetime, dict]] = {}   # (conversation, request id) -> result (duplicate delivery returns the same answer)
        self.lock = asyncio.Lock()
        self.notices: list[dict] = []                        # cancelled-missed timers etc., for the wrapper to show
        self.inhibited: str | None = None                    # set when the journal failed after a send: no more actions until restart
        self.mono_at: dict[str, float] = {}                  # task id -> monotonic time when set (this run only)
        self.recent: list[tuple[float, str, str, str]] = []  # (monotonic, conversation, tool, status) for the claim guard (memory only)
        self.recent_results: list[tuple[float, str, str, dict, dict]] = []   # (monotonic, conversation, tool, args, result): run_turn's record
        self.ready = False                                   # false until rebaseline() after HA has started: no timer runs before then

    # ---------- map ----------
    @staticmethod
    def _check_targets(targets: dict) -> dict:
        hs = targets.get('handles') or {}
        for h, t in hs.items():
            if not re.fullmatch(r'[a-z0-9_]+', h):
                raise ValueError(f'bad handle {h!r}')
            dom = ALLOWED_DOMAINS.get(t.get('kind'))
            if dom is None:
                raise ValueError(f'{h}: kind {t.get("kind")!r} is not allowed')
            if not t.get('entity_ids'):
                raise ValueError(f'{h}: no entities')
            for e in t['entity_ids']:
                if not e.startswith(dom + '.'):
                    raise ValueError(f'{h}: {e} is not in domain {dom}')
            for e in t.get('members', []) + list(t.get('expect', {})):
                if not e.startswith('light.'):
                    raise ValueError(f'{h}: scene member {e} is not a light')
            for e, w in (t.get('expect') or {}).items():
                if set(w) - EXPECT_KEYS or w.get('state') not in ('on', 'off'):
                    raise ValueError(f'{h}: expected state for {e} has unknown fields or no on/off')
            if t['kind'] == 'scene' and set(t.get('members', [])) != set(t.get('expect', {})):
                raise ValueError(f'{h}: scene members and expected states differ')
            if t['kind'] == 'blind':
                reviewed = targets.get('reviewed_covers') or {}
                for e in t['entity_ids']:
                    if e not in reviewed:
                        raise ValueError(f'{h}: {e} is not a reviewed cover')
                    cls = reviewed[e]
                    if not (cls in ALLOWED_COVER_CLASSES or (cls is None and targets.get('test_only') is True)):
                        raise ValueError(f'{h}: {e} reviewed class {cls!r} is not a blind')
                    if COVER_FORBIDDEN.search(e):
                        raise ValueError(f'{h}: {e} is named like a door, not a blind')
            for e in t['entity_ids'] + t.get('members', []):
                if FORBIDDEN.search(e):
                    raise ValueError(f'{h}: {e} matches the never-list')
        return hs

    def _target(self, handle: Any, kinds: tuple[str, ...]) -> tuple[dict | None, dict | None]:
        if not isinstance(handle, str) or handle not in self.handles:
            return None, _deny('unknown_target', "That isn't something I'm allowed to control.", handle=str(handle))
        t = self.handles[handle]
        if t['kind'] not in kinds:
            return None, _deny('wrong_kind', f"{t['label']} isn't controlled with that tool.", handle=handle)
        if not t.get('enabled', True):
            return None, _deny('not_enabled', f"I'm not allowed to control {t['label']} yet.", handle=handle, detail=t.get('disabled_reason'))
        return {**t, 'handle': handle, 'entity_ids': list(dict.fromkeys(t['entity_ids']))}, None

    # ---------- persistence ----------
    async def _save(self, after_send: bool = False) -> None:
        try:
            await self.store.save(self.data)
        except Exception as ex:
            raise JournalError(after_send, ex) from ex

    async def start(self) -> list[dict]:
        """Load the queue after a (re)start. Timers that fell due while HA was down are cancelled and reported; mid-dispatch ones are never
        replayed; undo receipts from before the restart can no longer be undone. Timers still to come wait for rebaseline()."""
        loaded = await self.store.load()
        if loaded:
            self.data = loaded
        now = self.now()
        changed = []
        for t in self.data['tasks']:
            if t['state'] == 'pending' and datetime.fromisoformat(t['due_at']) <= now:
                t.update(state='cancelled_missed', closed_at=now.isoformat(), reason='it fell due while Home Assistant was restarting')
                changed.append(t)
            elif t['state'] == 'dispatching':
                t.update(state='outcome_unknown', closed_at=now.isoformat(), reason='Home Assistant stopped while it was being sent, so it was not repeated')
                changed.append(t)
        for t in changed:
            self._close_notice(t)
        for r in self.data['receipts']:
            if r.get('phase') == 'sending':
                r['phase'] = 'outcome_unknown'
            r['restarted_since'] = True
        self._prune()
        await self._save()
        return changed

    async def rebaseline(self) -> list[dict]:
        """After HA has started (states are loaded, and every last_changed was reset by the restart): keep each timer still to come only if its
        target still looks exactly as it did when the timer was set, and take the new change revisions. Then timers may run."""
        out = []
        async with self.lock:
            keep = self.restart_policy == 'keep_if_unchanged'
            for t in self._pending():
                if not keep and t['id'] not in self.mono_at:     # set before this start: cancelled, never carried over
                    t.update(state='cancelled', closed_at=self.now().isoformat(), reason='Home Assistant restarted, so waiting timers were cancelled')
                    self._close_notice(t)
                    out.append(t)
                    continue
                same, revs = True, {}
                ahead = (datetime.fromisoformat(t['due_at']) - self.now()).total_seconds()
                if not t.get('snaps') or ahead > t.get('delay_seconds', LIMITS['maximum_delay_seconds']) + LIMITS['clock_disagreement_seconds']:
                    t.update(state='needs_review', closed_at=self.now().isoformat(),
                             reason='it could not be re-checked after the restart' if not t.get('snaps') else 'the clock changed')
                    self._close_notice(t)
                    out.append(t)
                    continue
                why = None
                for e, before in (t.get('snaps') or {}).items():
                    st = await self.backend.get_state(e)
                    s = _snap(st)
                    if s is None or s['state'] in ('unavailable', 'unknown'):
                        same, why = False, 'it could not be re-checked after the restart'
                        break
                    if not _same(s, before):
                        same, why = False, 'it changed while Home Assistant was restarting'
                        break
                    revs[e] = s['rev']
                if same:
                    t['revs'] = revs
                    self.mono_at[t['id']] = self.mono() - (self.now() - datetime.fromisoformat(t['created_at'])).total_seconds()
                else:
                    t.update(state='cancelled_changed', closed_at=self.now().isoformat(), reason=why)
                    self._close_notice(t)
                    out.append(t)
            self.ready = True
            await self._save()
        return out

    async def shutdown(self, reason: str = 'the Atlas coordinator was switched off or reloaded') -> list[dict]:
        """Disable, remove or reload: cancel every pending timer durably, so nothing comes back on a restart."""
        async with self.lock:
            out = []
            for t in self._pending():
                t.update(state='cancelled', closed_at=self.now().isoformat(), reason=reason)
                self._close_notice(t)
                out.append(t)
            await self._save()
            return out

    def _close_notice(self, t: dict) -> None:
        label = self._label_now(t) if t.get('what') else t['label']        # as of now, so a stale "tomorrow" isn't shown [R10-02]
        self._log('timer_' + t['state'], label, task=t['id'], reason=t.get('reason'))
        self.notices.append({'kind': t['state'], 'task': t['id'], 'label': label, 'due_at': t['due_at'], 'reason': t.get('reason')})

    def _prune(self) -> None:
        now = self.now()
        keep = timedelta(days=LIMITS['audit_retention_days'])
        self.data['log'] = [x for x in self.data['log'] if now - datetime.fromisoformat(x['at']) <= keep]
        self.data['receipts'] = [x for x in self.data['receipts'] if now - datetime.fromisoformat(x['at']) <= keep]
        self.data['tasks'] = [x for x in self.data['tasks'] if x['state'] == 'pending' or now - datetime.fromisoformat(x.get('closed_at') or x['created_at']) <= keep]
        self.requests = {k: v for k, v in self.requests.items() if (now - v[0]).total_seconds() <= LIMITS['request_memory_seconds']}

    def _log(self, event: str, label: str, **kw) -> None:
        self.data['log'].append({'at': self.now().isoformat(), 'event': event, 'label': label, **{k: v for k, v in kw.items() if v is not None}})

    # ---------- tool entry ----------
    async def call_tool(self, name: str, args: dict, *, conversation_id: str | None = None, user_text: str = '', turn: str | None = None,
                        last_reply: str | None = None, request_id: str | None = None, principal: str = 'household') -> dict:
        key = (conversation_id or 'none', request_id)
        if request_id and key in self.requests:
            return self.requests[key][1]
        fn = {'atlas_lights': self._lights, 'atlas_scene': self._scene, 'atlas_blind': self._blind, 'atlas_media': self._media,
              'atlas_confirm': self._confirm, 'atlas_schedule': self._schedule, 'atlas_scheduled': self._scheduled,
              'atlas_cancel': self._cancel, 'atlas_undo': self._undo}.get(name)
        from .tools import validate_args       # local import keeps tools.py and core.py independent at load time
        err = None if fn is None else validate_args(name, args, self.handles, self.timer_blinds)
        ctx = {'conversation_id': conversation_id or 'none', 'user_text': user_text or '', 'turn': turn, 'last_reply': last_reply, 'principal': principal}
        if fn is None:
            res = _deny('unknown_tool', "I can't do that.")
        elif err:
            res = _deny('bad_argument', "I couldn't understand that request exactly.", detail=err)
        elif name in ACTING and self.inhibited:
            res = _deny('inhibited', "I've stopped making changes because my action log couldn't be saved. Please tell the owner.", detail=self.inhibited)
        elif name in NEVER_SCOPE and NEVER_WORDS.search(ctx['user_text']):
            res = _deny('never_list', "Part of that is something I'm never allowed to do (locks, doors, alarms, gates or the energy system), so I haven't done any of it.")
        elif name in ('atlas_lights', 'atlas_schedule') and ctx['user_text'] and not self._in_scope(args.get('target_handle'), ctx['user_text']):
            t = self.handles[args['target_handle']]
            res = _r('needs_choice', f"Do you mean all of the {t['label'].lower()}, or just one room? Ask which.", reason='scope', handle=args['target_handle'],
                     label=t['label'])
        else:
            try:
                res = await fn(dict(args), ctx)
            except JournalError as je:
                if je.after_send:
                    self.inhibited = str(je)
                res = _r('failed' if not je.after_send else 'not_verified', "My action log couldn't be saved, so I can't confirm anything." if je.after_send
                         else "My action log couldn't be saved, so I didn't do anything.", reason='journal_unavailable')
            except Exception:
                # an unexpected error, perhaps after a send: the guard must not say nothing changed this turn [R14-03]
                self.recent = [x for x in self.recent if self.mono() - x[0] < 900] + [(self.mono(), conversation_id or 'none', name, 'tool_error')]
                raise
        self._log('tool', name, args=args, status=res['status'], reason=res.get('reason'), conversation=conversation_id, request=request_id)
        # the claim guard's evidence: a failed result that had sent something is 'failed_sent' (it may be described with a caveat) [R14-01]
        gst = 'failed_sent' if res['status'] == 'failed' and res.get('receipt') else res['status']
        self.recent = [x for x in self.recent if self.mono() - x[0] < 900] + [(self.mono(), conversation_id or 'none', name, gst)]
        self.recent_results = [x for x in self.recent_results if self.mono() - x[0] < 900] + [(self.mono(), conversation_id or 'none', name, dict(args), res)]
        self._prune()
        sent = res['status'] in ('done', 'undone', 'not_verified', 'cancelled', 'scheduled') or bool(res.get('receipt'))
        try:
            await self._save(after_send=sent)
        except JournalError as je:
            if sent:          # something may have changed and isn't durably recorded: stop acting until restart
                self.inhibited = str(je)
            if res['status'] in ('done', 'undone', 'cancelled', 'scheduled'):
                res = _r('not_verified', "My action log couldn't be saved, so I can't confirm that.", reason='journal_unavailable',
                         receipt=res.get('receipt'), handle=res.get('handle'), label=res.get('label'))
        if request_id:
            self.requests[key] = (self.now(), res)
        return res

    def _in_scope(self, handle: str, text: str) -> bool:
        """False when a floor-wide or whole-outside group is asked for in words that name neither its scope nor all the lights [M11]."""
        t = self.handles.get(handle) or {}
        if t.get('kind') != 'light' or len(set(t.get('entity_ids') or [])) < 2 or (t.get('area') and not t.get('floor')):
            return True
        said = f" {_words(text)} "
        if ALL_LIGHTS.search(text):
            return True
        base = set(_words(t.get('floor') or t['label'].split('(')[0]).split()) - {'lights', 'light', 'floor', 'the', 'and'}
        names = base | {x for w in base for x in SCOPE_SYNONYMS.get(w, ())}
        return any(f" {w} " in said for w in names)

    # ---------- shared ----------
    @staticmethod
    def _light_ok(op: str, pct: int | None):
        return _light_match({'state': 'off'} if op == 'off' else {'state': 'on', 'brightness_percent': pct})

    @staticmethod
    def _blind_ok(pos: int):
        def ok(st):
            if st is None:
                return False
            s = _snap(st)
            cur = _position(s)
            return cur is not None and s['state'] not in ('opening', 'closing') and abs(cur - pos) <= LIMITS['position_tolerance_percent']
        return ok

    async def _execute(self, t: dict, sends: list[tuple[str, str, list[str], dict]], checks: dict, befores: dict, ctx: dict, description: str,
                       already: list, missing: list, source: str = 'now', verify: bool = True, timeout: float | None = None, parent: str | None = None,
                       already_note: str = 'already were') -> dict:
        """One durable receipt (phase 'sending', saved BEFORE any send), one transport attempt per service call, then read-back of every entity."""
        rid = 'r_' + uuid.uuid4().hex[:8]
        receipt = {'id': rid, 'at': self.now().isoformat(), 'handle': t['handle'], 'kind': t['kind'], 'label': t['label'], 'description': description,
                   'befores': befores, 'phase': 'sending', 'conversation': ctx['conversation_id'], 'source': source, 'undone': False, 'parent': parent}
        self.data['receipts'].append(receipt)
        try:
            await self._save()
        except JournalError:
            self.data['receipts'].remove(receipt)
            raise
        failed_send, sent_ids = None, []
        for dom, svc, ids, data in sends:
            try:
                await self.backend.call(dom, svc, ids, data)
                sent_ids += ids
            except Exception as ex:          # one attempt only: never retried blindly, never another route
                failed_send = f'{type(ex).__name__}: {ex}'
                break
        results, after = {}, {}
        for e, pred in checks.items():
            if failed_send is None or e in sent_ids:      # a partial send still reads back what it did change [R8-04]
                st = await self.backend.wait_for(e, pred, timeout or LIMITS['readback_timeout_seconds'])
                results[e] = bool(pred(st))
                after[e] = _snap(st)
        if failed_send is not None:              # undo must only ever touch what this action really sent [R9-05]
            receipt['befores'] = {e: b for e, b in befores.items() if e in sent_ids}
            receipt['description'] = f"part of {description} ({len([e for e in befores if e in sent_ids])} of {len(befores)} lights)"
        receipt.update(phase='sent' if failed_send is None else ('partial' if sent_ids else 'send_failed'), after=after, verified=results)
        # A change Atlas made itself (and read back) is not a change "by hand": other pending timers on the same device take it as their new
        # baseline, so "off in 5, on in 10" both run. Anything else that changes the device still cancels them.
        for task in self._pending():
            for e, s in after.items():
                b = befores.get(e) or {}
                if e in (task.get('revs') or {}) and results.get(e) and s and task['revs'][e] == b.get('rev') and \
                        _same(b, (task.get('snaps') or {}).get(e)):      # not if something else changed it since the timer was set
                    task['revs'][e] = s['rev']
                    task.setdefault('snaps', {})[e] = s
        ok = [e for e, v in results.items() if v]
        bad = [e for e, v in results.items() if not v]
        base = {'handle': t['handle'], 'label': t['label'], 'changed': len(ok), 'already': len(already) or None, 'unavailable': len(missing) or None, 'receipt': rid}
        if failed_send and ok:
            return _r('failed', f"I couldn't reach all of {t['label']}: {len(ok)} changed and checked, the rest not.", detail=failed_send, **base)
        if failed_send:
            return _r('failed', f"I couldn't reach {t['label']}; nothing was confirmed.", detail=failed_send, **base)
        if not verify:
            return _r('not_verified', f"I've asked for {description}, but this device can't report back, so I can't confirm it.", **base)
        if bad:
            return _r('not_verified', f"I sent {description}, but {len(bad)} of {len(results)} didn't report back as asked.", not_confirmed=len(bad), **base)
        # a partial change leads with what changed, so it can't be relayed as "already" (C0e E12: "(23 already were)" was heard as "already off")
        extra = f", {len(ok)} of {len(ok) + len(already)} changed; the other {len(already)} {already_note}" if already else ''
        miss = f"; {len(missing)} not available, so not changed" if missing else ''
        return _r('done', f"Done: {description}{extra}{miss}. Checked.", **base)

    def _ask(self, ctx: dict, pending: dict, question: str, t: dict) -> dict:
        for k in [k for k, p in self.pending_confirmations.items() if p['conversation'] == ctx['conversation_id']]:
            self.replaced.setdefault(ctx['conversation_id'], []).append(self.pending_confirmations[k]['question'])
            del self.pending_confirmations[k]       # one open question per conversation: a new question replaces the old one
        cid = 'c_' + uuid.uuid4().hex[:6]
        self.pending_confirmations[cid] = {**pending, 'conversation': ctx['conversation_id'], 'turn': ctx.get('turn'), 'at': self.now(), 'question': question}
        return _r('needs_confirmation', f'Ask exactly: "{question}" and wait for a yes.', question=question, confirmation=cid, handle=t.get('handle'), label=t['label'])

    # ---------- lights ----------
    async def _lights(self, a: dict, ctx: dict, source: str = 'now') -> dict:
        t, err = self._target(a.get('target_handle'), ('light',))
        if err:
            return err
        op, pct = a['operation'], a.get('brightness_percent')
        if op in ('dim', 'brighten'):
            return await self._step(t, op, ctx, source)
        if op == 'brightness' and pct is None:
            return _deny('bad_argument', 'How bright, as a percentage?', detail='brightness needs brightness_percent')
        if op == 'brightness':
            op = 'on'
        ok = self._light_ok(op, pct)
        need, already, missing = [], [], []
        for e in t['entity_ids']:
            st = await self.backend.get_state(e)
            if st is None or st['state'] in ('unavailable', 'unknown'):
                missing.append(e)
            else:
                (already if ok(st) else need).append((e, _snap(st)))
        word = 'off' if op == 'off' else (f'on at {pct}%' if pct is not None else 'on')
        if not need:
            if not already:
                return _r('failed', f"{t['label']} isn't available right now.", reason='unavailable', handle=t['handle'], label=t['label'], unavailable=len(missing))
            if missing:
                return _r('skipped_already', f"{len(already)} of {len(t['entity_ids'])} in {t['label']} are already {word}; {len(missing)} aren't available "
                          f"right now, so I couldn't check or change them.", handle=t['handle'], label=t['label'], already=len(already), unavailable=len(missing))
            return _r('skipped_already', f"{t['label']} {'is' if len(t['entity_ids']) == 1 else 'are'} already {word}. I didn't change anything.",
                      handle=t['handle'], label=t['label'], already=len(already))
        ids = [e for e, _ in need]
        data = {} if op == 'off' or pct is None else {'brightness_pct': pct}
        sends = [('light', 'turn_off' if op == 'off' else 'turn_on', ids, data)]
        return await self._execute(t, sends, {e: ok for e in ids}, {e: s for e, s in need}, ctx, f"{t['label']} {word}", already, missing, source)

    async def _step(self, t: dict, op: str, ctx: dict, source: str) -> dict:
        """Dim or brighten each light one fixed step (20 points) from ITS current level, clamped to 1-100. Dimming never switches a light off
        and leaves off lights alone; brightening an off light turns it on at the step. The model does no arithmetic."""
        step = LIMITS['step_percent']
        # A full partition of the group, so every reply is derived from what each light really is [R9-01, R10-01]:
        #   gone        unavailable / unknown
        #   fixed_on    on/off-only light that is on   (can't be stepped; it is ON, so nothing may be called "off" or "already")
        #   fixed_off   on/off-only light that is off
        #   dim_on      dimmable and on, with its level
        #   dim_off     dimmable and off
        gone, fixed_on, fixed_off, dim_on, dim_off = [], [], [], {}, []
        snaps = {}
        for e in t['entity_ids']:
            st = await self.backend.get_state(e)
            if st is None or st['state'] in ('unavailable', 'unknown'):
                gone.append(e)
                continue
            s = snaps[e] = _snap(st)
            modes = st.get('attributes', {}).get('supported_color_modes') or []
            onoff = modes == ['onoff'] or (s['state'] == 'on' and s.get('brightness_percent') is None)
            if onoff:
                (fixed_on if s['state'] == 'on' else fixed_off).append(e)
            elif s['state'] == 'on':
                dim_on[e] = s['brightness_percent']
            else:
                dim_off.append(e)
        plan, at_limit = {}, []
        if op == 'dim':
            for e, cur in dim_on.items():
                (at_limit.append(e) if cur <= 1 else plan.__setitem__(e, max(1, cur - step)))
        else:
            for e, cur in dim_on.items():
                (at_limit.append(e) if cur >= 100 else plan.__setitem__(e, min(100, cur + step)))
            if not dim_on and not fixed_on:      # a dark room (nothing lit): brightening turns the dimmable lights on at the step
                for e in dim_off:
                    plan[e] = step
        word = 'dimmed' if op == 'dim' else 'brightened'

        def n(k, one, many):
            return f"{k} {one if k == 1 else many}"
        notes = []
        left_off = dim_off if (op == 'dim' or dim_on or fixed_on) else []
        if left_off:
            notes.append(f"{n(len(left_off), 'light was', 'lights were')} off and left off")
        if fixed_on or fixed_off:
            notes.append(f"{n(len(fixed_on) + len(fixed_off), 'light', 'lights')} can only switch on or off"
                         + (f", {len(fixed_on)} of them on" if fixed_on and fixed_off else ', and it is on' if fixed_on and len(fixed_on) == 1
                            else ', and they are on' if fixed_on else ''))
        if gone:
            notes.append(f"{n(len(gone), 'light', 'lights')} {'isn' if len(gone) == 1 else 'aren'}'t available right now")
        tail = f" ({'; '.join(notes)})" if notes else ''
        base = {'handle': t['handle'], 'label': t['label'], 'unavailable': len(gone) or None, 'not_dimmable': (len(fixed_on) + len(fixed_off)) or None,
                'left_off': len(left_off) or None}
        if not plan:
            if not snaps:
                return _r('failed', f"{t['label']} isn't available right now.", reason='unavailable', **base)
            if at_limit and not fixed_on:          # every lit light is dimmable and already at the limit: a true "already"
                why = 'the lowest level' if op == 'dim' else 'full brightness'
                which = 'The light that is on' if len(at_limit) == 1 else 'The lights that are on'
                return _r('skipped_already', f"{which} in {t['label']} {'is' if len(at_limit) == 1 else 'are'} already at {why}, so I didn't change anything{tail}.",
                          already=len(at_limit), **base)
            if not dim_on and not fixed_on and op == 'dim':     # nothing at all is lit: a true "already off"
                seen = 'Everything I can see' if gone else 'Everything'           # [R11-02]
                return _r('skipped_already', f"{seen} in {t['label']} is off, so there's nothing to dim{tail}.", already=len(snaps), **base)
            # what's lit can't be stepped (on/off only), or nothing here is dimmable: refuse, never "already" [R10-01, R11-01]
            verb = 'dim' if op == 'dim' else 'brighten'
            if fixed_on and at_limit:
                why = f"what's on either can only switch on or off or is already at {'the lowest level' if op == 'dim' else 'full brightness'}"
            elif fixed_on:
                why = "what's on can only switch on or off"
            else:
                why = f"nothing {'I can see ' if gone else ''}here can be dimmed or brightened"
            return _deny('not_supported', f"I can't {verb} {t['label']}: {why}{tail}.", **base)
        by_level = {}
        for e, want in plan.items():
            by_level.setdefault(want, []).append(e)
        sends = [('light', 'turn_on', ids, {'brightness_pct': lvl}) for lvl, ids in sorted(by_level.items())]
        levels = sorted(by_level)
        to = f'to {levels[0]}%' if len(levels) == 1 else f'one step each ({levels[0]}-{levels[-1]}%)'
        extra = f"; {n(len(at_limit), 'was', 'were')} already at {'the lowest level' if op == 'dim' else 'full brightness'}" if at_limit else ''
        tail2 = f" ({'; '.join(notes)}{extra})" if notes else (f" ({extra[2:]})" if extra else '')
        res = await self._execute(t, sends, {e: self._light_ok('on', want) for e, want in plan.items()}, {e: snaps[e] for e in plan},
                                  ctx, f"{t['label']} {word} {to}", [], [], source)
        if res['status'] == 'done':
            res['summary'] = f"Done: {t['label']} {word} {to}{tail2}. Checked."
            res['levels'] = dict(plan)
        res.update({k: v for k, v in base.items() if v is not None and k not in ('handle', 'label')})
        return res

    # ---------- scenes ----------
    async def _scene(self, a: dict, ctx: dict, source: str = 'now') -> dict:
        t, err = self._target(a.get('recipe_handle'), ('scene',))
        if err:
            return err
        expect = t.get('expect') or {}
        if not expect:
            return _deny('not_reviewed', f"I can't run {t['label']} yet: its lights haven't been checked.", handle=t['handle'])
        for sid in t['entity_ids']:
            sc = await self.backend.get_state(sid)
            live = (sc or {}).get('attributes', {}).get('entity_id')
            if sc is None or (live is not None and set(live) != set(t.get('members') or expect)) or \
                    (live is None and t.get('contents_frozen_offline') is not True):
                # its contents differ from what was reviewed (e.g. a helper or script added), or can't be read and weren't frozen offline [RT034]
                return _deny('scene_changed', f"I can't run {t['label']}: what it does no longer matches what was checked.", handle=t['handle'])
        befores, need, already = {}, [], []
        checks = {m: _light_match(w) for m, w in expect.items()}
        for m in expect:
            st = await self.backend.get_state(m)
            if st is None or st['state'] in ('unavailable', 'unknown'):
                return _r('failed', f"Part of {t['label']} isn't available right now, so I didn't run it.", reason='unavailable', handle=t['handle'], label=t['label'])
            befores[m] = _snap(st)
            (already if checks[m](st) else need).append(m)
        if not need:
            return _r('skipped_already', f"{t['label']} is already set. I didn't change anything.", handle=t['handle'], label=t['label'], already=len(already))
        return await self._execute(t, [('scene', 'turn_on', t['entity_ids'], {})], checks, befores, ctx, f"the {t['label']} scene", already, [], source)

    # ---------- blinds ----------
    async def _blind_plan(self, t: dict, op: str, position: int | None):
        """(need, already, pos, word) or (None, result). need = [(entity, before-image)]."""
        pos = 100 if op == 'open' else 0 if op == 'close' else position
        if pos is None:
            return None, _deny('bad_argument', 'To what position, as a percentage open?', detail='position needs position_percent')
        need, already = [], []
        for e in t['entity_ids']:
            st = await self.backend.get_state(e)
            if st is None or st['state'] in ('unavailable', 'unknown'):
                return None, _r('failed', f"{t['label']} isn't available right now.", reason='unavailable', handle=t['handle'], label=t['label'])
            if st.get('attributes', {}).get('device_class') != self.reviewed_covers.get(e, '\x00'):     # still the class it was reviewed with [H2]
                return None, _deny('not_reviewed_cover', f"{t['label']} isn't the blind I was set up for, so I won't move it.", handle=t['handle'])
            if op == 'position' and not int(st.get('attributes', {}).get('supported_features') or 0) & 4:     # CoverEntityFeature.SET_POSITION
                return None, _deny('not_supported', f"{t['label']} can only open or close fully.", handle=t['handle'])
            s = _snap(st)
            if s['state'] in ('opening', 'closing'):
                return None, _deny('moving', f"{t['label']} is moving right now; ask again when it stops.", handle=t['handle'])
            if _position(s) is None:
                return None, _deny('position_unknown', f"I can't tell where {t['label']} is, so I won't move it.", handle=t['handle'])
            (already if abs(_position(s) - pos) <= LIMITS['position_tolerance_percent'] else need).append((e, s))
        word = 'open' if pos == 100 else 'closed' if pos == 0 else f'{pos}% open'
        if not need:
            return None, _r('skipped_already', f"{t['label']} {'is' if len(t['entity_ids']) == 1 else 'are'} already {word}. I didn't change anything.",
                            handle=t['handle'], label=t['label'], already=len(already))
        return (need, already, pos, word), None

    async def _blind_send(self, t, plan, ctx, source='now', parent=None):
        need, already, pos, word = plan
        ids = [e for e, _ in need]
        svc, data = ('open_cover', {}) if pos == 100 else ('close_cover', {}) if pos == 0 else ('set_cover_position', {'position': pos})
        return await self._execute(t, [('cover', svc, ids, data)], {e: self._blind_ok(pos) for e in ids}, {e: s for e, s in need}, ctx,
                                   f"{t['label']} {word}", already, [], source, verify=not t.get('assumed_state'),
                                   timeout=LIMITS['blind_readback_timeout_seconds'], parent=parent)

    async def _blind(self, a: dict, ctx: dict) -> dict:
        t, err = self._target(a.get('target_handle'), ('blind',))
        if err:
            return err
        plan, res = await self._blind_plan(t, a['operation'], a.get('position_percent'))
        if res:
            return res
        need, _, pos, word = plan
        q = (f"{'Open' if pos == 100 else 'Close'} the {t['label'].lower()}?" if pos in (0, 100) else f"Set the {t['label'].lower()} to {pos}% open?")
        return self._ask(ctx, {'kind': 'blind_now', 'args': a, 'preview': {e: s['rev'] for e, s in need}, 'preview_snaps': {e: s for e, s in need}}, q, t)

    async def _confirm(self, a: dict, ctx: dict) -> dict:
        cid = a['confirmation']
        p = self.pending_confirmations.get(cid)
        if p is None:
            return _deny('no_such_confirmation', "There's nothing waiting for a yes.")
        if p['conversation'] != ctx['conversation_id']:
            return _deny('other_conversation', "That question was asked somewhere else; ask again here.")
        if (self.now() - p['at']).total_seconds() > LIMITS['confirmation_seconds']:
            self.pending_confirmations.pop(cid, None)
            return _deny('confirmation_expired', 'That question has timed out. Ask again if you still want it.')
        if p.get('turn') is None or ctx.get('turn') is None or ctx['turn'] == p['turn']:
            return _deny('no_plain_yes', 'Ask the question and wait for the answer first.', question=p['question'])   # the yes must be a later turn
        if _words(p['question']) not in _words(ctx.get('last_reply') or ''):
            return _deny('question_not_asked', f'Ask exactly: "{p["question"]}" and wait for a yes.', question=p['question'])   # the yes answers THIS question [RT116]
        if any(_words(q) != _words(p['question']) and _words(q) in _words(ctx.get('last_reply') or '') for q in self.replaced.get(ctx['conversation_id'], [])):
            self.pending_confirmations.pop(cid, None)
            self.replaced.pop(ctx['conversation_id'], None)
            return _r('needs_choice', 'That yes could answer more than one question. Ask again about just one.', question=p['question'])   # [RT114]
        if not AFFIRMATIVE.match(ctx['user_text'] or ''):
            return _deny('no_plain_yes', 'I need a plain "yes" from you before I do that.', question=p['question'])
        self.pending_confirmations.pop(cid, None)      # consumed once
        self.replaced.pop(ctx['conversation_id'], None)
        if p['kind'] == 'blind_now':
            t, err = self._target(p['args']['target_handle'], ('blind',))
            if err:
                return err
            plan, res = await self._blind_plan(t, p['args']['operation'], p['args'].get('position_percent'))
            if res:
                return res
            if {e: s['rev'] for e, s in plan[0]} != p['preview'] or \
                    any(not _same(s, p['preview_snaps'].get(e)) for e, s in plan[0]):      # act only on the frozen preview [R8-08, cloud review 1 m1]
                return _deny('changed_since_question', f"{t['label']} changed since I asked, so I haven't moved it. Ask again if you still want it.")
            return await self._blind_send(t, plan, ctx)
        if p['kind'] == 'schedule':
            t, err = self._target(p['args']['target_handle'], ('light', 'scene', 'blind'))
            if err:
                return err
            now_snaps = {e: _snap(await self.backend.get_state(e)) for e in t.get('entity_ids', [])}
            now_revs = {e: (s or {}).get('rev') for e, s in now_snaps.items()}
            moved = any(not _same(now_snaps.get(e), s) for e, s in (p.get('preview_snaps') or {}).items())     # [R8-08]
            if p.get('preview') is not None and (now_revs != p['preview'] or moved):     # the yes is bound to the plan as asked [RT116/RT120]
                return _deny('changed_since_question', f"{t.get('label', 'That')} changed since I asked, so I haven't set the timer. Ask again if you still want it.")
            due = datetime.fromisoformat(p['due'])          # the exact time the person agreed to [R8-07]
            if not 0 < (due - self.now()).total_seconds() <= LIMITS['maximum_delay_seconds']:
                return _deny('changed_since_question', 'That time has passed since I asked; ask again.')
            return await self._enqueue(p['args'], ctx, confirmed=True, due=due)
        if p['kind'] == 'undo':
            return await self._undo_receipt(p['receipt'], ctx)
        return _deny('no_such_confirmation', "There's nothing waiting for a yes.")

    async def _media(self, a: dict, ctx: dict) -> dict:
        t, err = self._target(a.get('target_handle'), ('media',))
        if err:
            return err
        # Media is a later v1 group: no media action exists until each player's inverse is proven.
        return _deny('not_enabled', f"I'm not allowed to control {t['label']} yet.", handle=a['target_handle'])

    # ---------- timers ----------
    def _due(self, a: dict) -> tuple[datetime | None, dict | None]:
        now = self.now()
        if a.get('in_minutes') is not None:
            due = now + timedelta(minutes=a['in_minutes'])
        else:
            hh, mm = map(int, a['at_time'].split(':'))
            local = now.astimezone(self.tz)

            def odd(d):     # the civil time hh:mm on day d is skipped (spring forward) or doubled (fall back) by a daylight-saving change
                naive = datetime(d.year, d.month, d.day, hh, mm)
                f0, f1 = naive.replace(tzinfo=self.tz, fold=0), naive.replace(tzinfo=self.tz, fold=1)
                return f0.utcoffset() != f1.utcoffset() or f0.astimezone(timezone.utc).astimezone(self.tz).replace(tzinfo=None) != naive, f0, f1
            today_odd, t0, t1 = odd(local.date())
            skipped_today = today_odd and t0.astimezone(timezone.utc).astimezone(self.tz).replace(tzinfo=None) != t0.replace(tzinfo=None)
            still_ahead = (hh, mm) > (local.hour, local.minute) if skipped_today else max(_utc(t0), _utc(t1)) > now   # [R5-03]
            if today_odd and still_ahead:      # today's skipped hour still ahead, or the doubled hour's second occurrence [R4-02]
                return None, _r('needs_choice', 'That time happens twice (or not at all) tonight because of the clock change. Say it in minutes from now instead.',
                                reason='ambiguous_time')
            if (hh, mm) == (local.hour, local.minute):      # this very minute: now, or tomorrow? ask [R8-01]
                return None, _r('needs_choice', 'That time is now. Do you mean right now, or this time tomorrow?', reason='ambiguous_time')
            day = local.date() if (hh, mm) > (local.hour, local.minute) else local.date() + timedelta(days=1)
            is_odd, first, _second = odd(day)
            if is_odd:      # ask, before any cap is applied [RT066, RT068]
                return None, _r('needs_choice', 'That time happens twice (or not at all) because of the clock change. Say it in minutes from now instead.',
                                reason='ambiguous_time')
            due = first
        due = _utc(due)                                 # one time base for every stored and compared due time
        secs = (due - now).total_seconds()
        if secs <= 0 or secs > LIMITS['maximum_delay_seconds']:
            return None, _deny('too_far', 'I can only set timers up to 24 hours ahead.', detail=f'{round(secs / 60)} minutes')
        return due, None

    async def _schedule(self, a: dict, ctx: dict) -> dict:
        t, err = self._target(a.get('target_handle'), ('light', 'scene', 'blind') if self.timer_blinds else ('light', 'scene'))
        if err:
            return err
        if t['kind'] == 'scene' and not t.get('expect'):
            return _deny('not_reviewed', f"I can't run {t['label']} yet: its lights haven't been checked.", handle=t['handle'])
        ok_ops = {'light': ('on', 'off'), 'scene': ('on',), 'blind': ('open', 'close')}[t['kind']]
        if a['operation'] not in ok_ops:
            return _deny('not_allowed_in_schedule', f"A timer can only {' or '.join(ok_ops)} {t['label']}.", handle=t['handle'])
        due, err = self._due(a)
        if err:
            return err
        same = self._same_timer(a, due)
        if same:      # an identical action at the same time is already waiting: ask instead of queueing it twice [RT076]
            return _r('needs_choice', f"There's already a timer for that: {self._label_now(same[0])}. Keep it, or say \"cancel that\" first if you want a different time.",
                      tasks=[{'task': x['id'], 'label': self._label_now(x)} for x in same])
        if len(self._pending()) >= LIMITS['maximum_pending_tasks']:
            return _deny('too_many_pending', 'There are already 10 timers waiting. Cancel one first.')
        if t['kind'] == 'blind':
            _plan, res = await self._blind_plan(t, a['operation'], None)
            if res is not None and res.get('reason') in ('unavailable', 'moving', 'position_unknown', 'not_supported'):
                return res
            q = f"{'Open' if a['operation'] == 'open' else 'Close'} the {t['label'].lower()} at {_when(due, self.now(), self.tz)}?"
            snaps = {e: _snap(await self.backend.get_state(e)) for e in t['entity_ids']}
            preview = {e: (s or {}).get('rev') for e, s in snaps.items()}
            return self._ask(ctx, {'kind': 'schedule', 'args': a, 'preview': preview, 'preview_snaps': snaps, 'due': due.isoformat()}, q, t)
        return await self._enqueue(a, ctx)

    async def _enqueue(self, a: dict, ctx: dict, confirmed: bool = False, due: datetime | None = None) -> dict:
        t, err = self._target(a['target_handle'], ('light', 'scene', 'blind'))
        if err:
            return err
        t = self.handles[a['target_handle']]
        if due is None:
            due, err = self._due(a)
            if err:
                return err
        if len(self._pending()) >= LIMITS['maximum_pending_tasks']:
            return _deny('too_many_pending', 'There are already 10 timers waiting. Cancel one first.')
        word = {'on': 'on', 'off': 'off', 'open': 'open', 'close': 'closed'}[a['operation']]
        what = f"{t['label']} {'scene' if t['kind'] == 'scene' else word}"
        label = f"{what} at {_when(due, self.now(), self.tz)}"
        watch = list(t.get('expect') or t['entity_ids'])
        snaps = {e: _snap(await self.backend.get_state(e)) for e in watch}
        if self._same_timer(a, due):
            return _r('needs_choice', 'There is already a timer for that.', tasks=[])
        tid = 'T' + uuid.uuid4().hex[:5].upper()
        task = {'id': tid, 'state': 'pending', 'created_at': self.now().isoformat(), 'due_at': due.isoformat(), 'delay_seconds': round((due - self.now()).total_seconds()),
                'handle': a['target_handle'], 'operation': a['operation'], 'label': label, 'what': what, 'conversation': ctx['conversation_id'], 'confirmed': confirmed,
                'digest': _digest(t), 'snaps': snaps, 'revs': {e: (s or {}).get('rev') for e, s in snaps.items()}}
        self.data['tasks'].append(task)
        try:
            await self._save()
        except JournalError:
            self.data['tasks'].remove(task)       # never acknowledge a timer that isn't durably recorded
            raise
        self.mono_at[tid] = self.mono()
        return _r('scheduled', f"Timer set: {label}. Say \"cancel that\" to stop it.", task=tid, label=label, due_local=_when(due, self.now(), self.tz))

    def _same_timer(self, a: dict, due: datetime) -> list[dict]:
        return [x for x in self._pending() if x['handle'] == a['target_handle'] and x['operation'] == a['operation']
                and abs((datetime.fromisoformat(x['due_at']) - due).total_seconds()) <= 60]

    def _label_now(self, x: dict) -> str:
        """A waiting timer's label as of NOW (a stored 'tomorrow' goes stale after midnight) [R9-02]."""
        return f"{x['what']} at {_when(datetime.fromisoformat(x['due_at']), self.now(), self.tz)}" if x.get('what') else x['label']

    def _pending(self) -> list[dict]:
        return sorted([x for x in self.data['tasks'] if x['state'] == 'pending'], key=lambda x: datetime.fromisoformat(x['due_at']))

    async def _scheduled(self, a: dict, ctx: dict) -> dict:
        p = self._pending()
        recent = [x for x in self.data['tasks'] if x['state'] in ('cancelled_missed', 'outcome_unknown', 'cancelled_changed', 'needs_review') or
                  (x['state'] == 'cancelled' and x.get('reason') != 'cancelled by request') or
                  (x['state'] == 'ran' and x.get('result') not in ('done', 'skipped_already'))]
        recent = [x for x in recent if
                  (self.now() - datetime.fromisoformat(x['closed_at'])).total_seconds() < 6 * 3600]
        items = [{'task': x['id'], 'label': self._label_now(x), 'due_local': _when(datetime.fromisoformat(x['due_at']), self.now(), self.tz)} for x in p]
        said = {'did_not_run': "it didn't run", 'could_not_reach': "it couldn't reach the device", 'ran_not_confirmed': "it ran but couldn't be confirmed"}
        missed = [{'task': x['id'], 'label': x.get('what') or x['label'], 'what_happened': x['reason'] if x['state'] != 'ran' else
                   f"{said.get(x.get('outcome'), 'it ran but could not be confirmed')}: {x.get('result_summary') or x.get('result')}"} for x in recent] or None
        if not items:
            return _r('scheduled_list', 'Nothing is scheduled.', tasks=[], missed=missed)
        return _r('scheduled_list', f"{len(items)} timer{'s' if len(items) != 1 else ''} waiting: " + '; '.join(x['label'] for x in items) + '.', tasks=items, missed=missed)

    async def _cancel(self, a: dict, ctx: dict) -> dict:
        async with self.lock:
            p = self._pending()
            tid = a.get('task')
            if tid is None:
                mine = [x for x in p if x['conversation'] == ctx['conversation_id']]
                busy = [x for x in self.data['tasks'] if x['state'] == 'dispatching' and x['conversation'] == ctx['conversation_id']]
                if not mine and busy:
                    return _deny('too_late', f"Too late: {busy[-1].get('what') or busy[-1]['label']} is happening now.", task=busy[-1]['id'])
                if not mine and p:     # nothing set here: "that" can't refer to another conversation's timer [R4-04]
                    return _r('needs_choice', 'Which one? ' + '; '.join(self._label_now(x) for x in p) + '.', tasks=[{'task': x['id'], 'label': self._label_now(x)} for x in p])
                pool = mine
                if len(pool) > 1:      # more than one could be "that": ask, never guess [RT073]
                    return _r('needs_choice', 'Which one? ' + '; '.join(self._label_now(x) for x in pool) + '.', tasks=[{'task': x['id'], 'label': self._label_now(x)} for x in pool])
                if not pool:
                    return _deny('nothing_scheduled', 'Nothing is scheduled to cancel.')
                task = pool[0]
            else:
                task = next((x for x in self.data['tasks'] if x['id'] == tid), None)
                if task is None:
                    return _deny('no_such_task', "I can't find that timer.")
                if task['state'] == 'dispatching':
                    return _deny('too_late', f"Too late: {task.get('what') or task['label']} is happening now.", task=tid)
                if task['state'] != 'pending':
                    return _deny('not_pending', f"{task.get('what') or task['label']} isn't waiting any more ({task['state'].replace('_', ' ')}).", task=tid)
            task.update(state='cancelled', closed_at=self.now().isoformat(), reason='cancelled by request')
            await self._save()
            now_label = self._label_now(task)
            return _r('cancelled', f"Cancelled: {now_label}.", task=task['id'], label=now_label)

    async def _still_valid(self, task: dict) -> tuple[str, str] | None:
        t = self.handles.get(task['handle'])
        if t is None or not t.get('enabled', True) or _digest(t) != task.get('digest'):
            return 'the list of allowed devices changed after it was set', 'needs_review'
        if t['kind'] != 'blind':
            # the owner (directive 1151 am. 1, "Let's go with your recommendation"): light and scene timers run at the due time even if something
            # else changed the light meanwhile; lights already in the target state are skipped (fresh read, read-back and log as usual).
            return None
        for e, rev in (task.get('revs') or {}).items():      # blinds keep the fire-time re-check he approved
            st = await self.backend.get_state(e)
            if (st or {}).get('last_changed') != rev or not _same(_snap(st), (task.get('snaps') or {}).get(e)):
                return 'it was changed after the timer was set, by something other than Atlas', 'cancelled_changed'
        return None

    async def tick(self) -> list[dict]:
        """Run every timer now due (the wrapper calls this at each due time). Returns what happened to each."""
        out = []
        if not self.ready:
            return out
        tick_at = self.now()
        for task in self._pending():
            async with self.lock:
                if task['state'] != 'pending':          # cancelled while we waited for the lock
                    continue
                now = self.now()
                due = datetime.fromisoformat(task['due_at'])
                # a timer that fell due while this tick was still sending and reading back an earlier one (a blind takes up to 45 s) is judged as
                # of when its turn came, not as late: HA was up the whole time [cloud review 1, M9]. Lateness before the tick still counts.
                busy = max(0.0, (now - max(due, tick_at)).total_seconds()) if due <= now else 0.0
                late = (now - due).total_seconds() - busy
                ran_for = self.mono() - self.mono_at[task['id']] if task['id'] in self.mono_at else None
                wall_for = (now - datetime.fromisoformat(task['created_at'])).total_seconds()
                why, state = None, None
                if self.inhibited:
                    why, state = 'the action log could not be saved', 'cancelled_missed'
                elif (due - now).total_seconds() > LIMITS['maximum_delay_seconds'] + LIMITS['clock_disagreement_seconds'] or \
                        (ran_for is not None and abs(ran_for - wall_for) > LIMITS['clock_disagreement_seconds']):
                    why, state = 'the clock changed', 'needs_review'
                elif ran_for is not None and ran_for - busy > task.get('delay_seconds', LIMITS['maximum_delay_seconds']) + LIMITS['maximum_uptime_lateness_seconds']:
                    why, state = f"it would have run {round(ran_for - busy - task.get('delay_seconds', 0))} s late", 'cancelled_missed'
                elif due > now:
                    continue
                elif late > LIMITS['maximum_uptime_lateness_seconds']:
                    why, state = f'it would have run {round(late)} s late', 'cancelled_missed'
                else:
                    why, state = (await self._still_valid(task)) or (None, None)
                if why:
                    task.update(state=state, closed_at=now.isoformat(), reason=why)
                    self._close_notice(task)
                    await self._save()
                    out.append({'task': task['id'], 'status': state, 'reason': why})
                    continue
                task['state'] = 'dispatching'
                try:
                    await self._save()   # durable before the send: a crash now becomes outcome_unknown, never a replay
                except JournalError as je:   # nothing sent: close it visibly and stop further timers, as other log failures do [R6-01]
                    self.inhibited = str(je)
                    task.update(state='cancelled_missed', closed_at=now.isoformat(), reason='the action log could not be saved, so it did not run',
                                outcome='did_not_run')
                    self.notices.append({'kind': 'did_not_run', 'task': task['id'], 'label': task.get('what') or task['label'], 'due_at': task['due_at'], 'reason': task['reason']})
                    out.append({'task': task['id'], 'status': 'cancelled_missed', 'reason': task['reason']})
                    continue
            t, _ = self._target(task['handle'], ('light', 'scene', 'blind'))
            ctx = {'conversation_id': task['conversation'], 'user_text': '', 'turn': None, 'last_reply': None, 'principal': 'timer'}
            src = f"timer {task['id']}"
            try:
                if t is None:
                    res = _deny('not_enabled', 'That target is no longer allowed.')
                elif t['kind'] == 'light':
                    res = await self._lights({'target_handle': task['handle'], 'operation': task['operation']}, ctx, source=src)
                elif t['kind'] == 'scene':
                    res = await self._scene({'recipe_handle': task['handle']}, ctx, source=src)
                elif t['kind'] != 'blind' or not self.timer_blinds or not task.get('confirmed'):
                    res = _deny('no_plain_yes', 'Blind timers need a yes when set.')
                else:
                    plan, res = await self._blind_plan(t, task['operation'], None)
                    if res is None:
                        res = await self._blind_send(t, plan, ctx, source=src)
            except JournalError as je:
                self.inhibited = str(je)
                res = _r('failed', "The action log couldn't be saved.", reason='journal_unavailable')
            task.update(state='ran', closed_at=self.now().isoformat(), result=res['status'], reason=res.get('reason'), receipt=res.get('receipt'))
            task['result_summary'] = res.get('summary')
            if res['status'] not in ('done', 'skipped_already'):      # never silently [R4-01]; say what really happened [R5-01]
                kind = ('did_not_run' if not res.get('receipt') else 'could_not_reach' if res['status'] == 'failed' else 'ran_not_confirmed')
                task['outcome'] = kind
                self.notices.append({'kind': kind, 'task': task['id'], 'label': task.get('what') or task['label'], 'due_at': task['due_at'],
                                     'reason': res.get('summary') or res['status']})
            self._log('timer_ran', task['label'], task=task['id'], status=res['status'])
            try:
                await self._save(after_send=True)
            except JournalError as je:
                self.inhibited = str(je)
            out.append({'task': task['id'], **res})
        return out

    def results_since(self, mono_start: float, conversation_id: str | None) -> list[tuple[str, dict, dict]]:
        """(tool, args, result) of every atlas_ tool call in this conversation since mono_start (the Atlas-side project's scorer; run_turn's tool_results)."""
        return [(n, a, r) for t, c, n, a, r in self.recent_results if t >= mono_start and c == (conversation_id or 'none')]

    def statuses_since(self, mono_start: float, conversation_id: str | None) -> list[str]:
        """Statuses of atlas_ tool results in this conversation since mono_start (the claim guard's evidence for one turn)."""
        return [st for t, c, _n, st in self.recent if t >= mono_start and c == (conversation_id or 'none')]

    def evidence_since(self, mono_start: float, conversation_id: str | None) -> list[tuple[str, str]]:
        """(tool, status) of atlas_ tool results in this conversation since mono_start: what guard_reply needs to tell a lights result from a
        blind one [cloud review 1, M8]. The guarded agent should pass this instead of statuses_since()."""
        return [(n, st) for t, c, n, st in self.recent if t >= mono_start and c == (conversation_id or 'none')]

    def next_due(self) -> datetime | None:
        p = self._pending()
        return datetime.fromisoformat(p[0]['due_at']) if p else None

    # ---------- undo ----------
    async def _undo(self, a: dict, ctx: dict) -> dict:
        now = self.now()
        live = [r for r in self.data['receipts'] if not r['undone'] and r['phase'] in ('sent', 'partial') and r.get('befores') and not r.get('is_undo')
                and (now - datetime.fromisoformat(r['at'])).total_seconds() < LIMITS['undo_seconds']]
        if a.get('receipt'):
            r = next((x for x in self.data['receipts'] if x['id'] == a['receipt']), None)
            if r is None:
                return _deny('no_such_receipt', "I can't find that action.")
            if r not in live:
                return _deny('undo_expired', f"I can only undo things for 10 minutes; {r['description']} is too old or already undone.")
        else:
            if not live:
                return _deny('nothing_to_undo', "There's nothing from the last 10 minutes to undo.")
            mine = [x for x in live if x.get('conversation') == ctx['conversation_id']]      # as cancel [R4-04]: never another room's action [M10]
            if not mine:
                return _deny('not_here', "The last change wasn't made here, so I can't undo it from here.")
            r = mine[-1]       # the latest action by creation order (receipts are appended in order; times can tie)
        if r.get('restarted_since'):
            return _deny('restarted', f"Home Assistant restarted since {r['description']}, so I can't undo it safely.", receipt=r['id'])
        if r.get('kind') == 'blind':
            return self._ask(ctx, {'kind': 'undo', 'receipt': r['id']}, f"Put the {r['label'].lower()} back as it was?", {'handle': r['handle'], 'label': r['label']})
        return await self._undo_receipt(r['id'], ctx)

    async def _undo_receipt(self, rid: str, ctx: dict) -> dict:
        r = next((x for x in self.data['receipts'] if x['id'] == rid), None)
        if r is None or r['undone'] or r.get('restarted_since') or (self.now() - datetime.fromisoformat(r['at'])).total_seconds() >= LIMITS['undo_seconds']:
            return _deny('undo_expired', "That can't be undone any more.")
        sends, checks, befores, blocked = [], {}, {}, []
        for e, before in r['befores'].items():
            if before is None:
                continue
            want = (r.get('after') or {}).get(e)
            st = await self.backend.get_state(e)
            now = _snap(st)
            if not want or now is None or not (r.get('verified') or {}).get(e) or now.get('rev') != want.get('rev') or not _same(now, want):
                blocked.append(e)          # changed since (even if it is back to the same state), or never confirmed: leave it alone
                continue
            dom = e.split('.')[0]
            befores[e] = now
            if dom == 'light':
                svc, data, w = _light_restore(before, now)
                sends.append(('light', svc, [e], data))
                checks[e] = _light_match(w)
            elif dom == 'cover' and (st or {}).get('attributes', {}).get('device_class') != self.reviewed_covers.get(e, '\x00'):
                blocked.append(e)          # no longer the class it was reviewed with: leave it alone [R12-13]
                continue
            elif dom == 'cover' and _position(before) is not None:
                pos = _position(before)
                if before.get('position_percent') is not None and pos not in (0, 100):
                    sends.append(('cover', 'set_cover_position', [e], {'position': pos}))
                else:
                    sends.append(('cover', 'open_cover' if pos == 100 else 'close_cover', [e], {}))
                checks[e] = self._blind_ok(pos)
        if not sends:
            return _deny('changed_since', f"I can't undo {r['description']}: it's been changed since.", receipt=r['id'])
        t = {'handle': r['handle'], 'kind': r['kind'], 'label': r['label']}
        res = await self._execute(t, sends, checks, befores, ctx, f"{r['description']} undone", [], [], source='undo', parent=r['id'],
                                  timeout=LIMITS['blind_readback_timeout_seconds'] if r['kind'] == 'blind' else None)
        ur = next((x for x in self.data['receipts'] if x['id'] == res.get('receipt')), None)
        if ur is not None:
            ur['is_undo'] = True
        if (ur or {}).get('phase') != 'send_failed':      # nothing was sent: the action can still be undone [cloud review 1, m2]
            r['undone'] = True
            r['undone_by'] = res.get('receipt')
        part = f" ({len(blocked)} left alone because they were changed since)" if blocked else ''
        if res['status'] == 'done':
            return _r('undone', f"Undone: {r['description']}{part}. Checked.", receipt=res['receipt'], parent=r['id'], restored=len(checks), left_alone=len(blocked) or None)
        return {**res, 'summary': res['summary'] + part, 'parent': r['id']}
