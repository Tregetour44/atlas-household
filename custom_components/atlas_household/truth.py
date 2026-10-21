"""The truth check (cloud robustness job, 21 Oct): the claim guard reads claim WORDINGS; this reads the device states. After a model turn,
a clause that states a device's state ("Office lights are off.", "The sunroom blind's down.", "Good Night is on.", "They're all closed now.")
or a timer ("Righto, office lights off at nine.", "They'll switch off in ten.") is compared with Home Assistant's state and the timer queue
as they are now, and a clause that is false is dropped. A true statement passes, however it is worded (a status answer from the readings,
the coordinator's own summary, a verbless "Lights off."). Pure Python: the caller passes the states it read (entity -> HA state dict), the
pending timers, the handles, the person's words and this turn's tool results.

What is checked, and what is left alone:
  - the subject is a handle named in the clause (its label, its room's lights, a blind's own words, a scene's name), or a pronoun ("it",
    "they", "both", "all of them") that resolves to the handles this turn's tools acted on, else to the ONE handle the person's words named;
  - lights: "off" is false if any of the handle's lights is on; "on" if none is; "at N%" if any lit light is more than 2 points from N;
    blinds: "closed/down/shut" is false if any is open more than 3%; "open/up" if all are closed; "at N%" if any is more than 3 points off;
    a scene: "on/running/set/active" is false if any member doesn't match its reviewed state;
  - timers: a clause with a time and an on/off/open/close word is false when no pending timer exists for the handle (or, for a pronoun with
    nothing to resolve, none at all with that operation);
  - never a question, a negated or conditional clause, a future offer, or a past statement ("were off at 9", "earlier").
"""
from __future__ import annotations

import re

_NUMS = r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|forty-five|fifty|sixty|\d+)"
TIME = re.compile(r"\b(?:at\s+(?:\d{1,2}(?:[:.]\d\d)?(?![\d%])(?!\s*(?:%|percent|per\s*cent))|(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b"
                  r"(?!\s*(?:%|percent|per\s*cent))|noon|midnight|midday|half\s+past\s+\w+|quarter\s+(?:past|to)\s+\w+)|"
                  r"by\s+(?:\d{1,2}|" + _NUMS + r"|noon|midnight)|in\s+(?:" + _NUMS + r"|an?|half\s+an)(?:\s+(?:minutes?|mins?|hours?|hrs?))?\b|"
                  r"" + _NUMS + r"\s+(?:minutes?|mins?|hours?)|tonight|tomorrow|later\b|(?:\d{1,2}|" + _NUMS + r")\s*(?:am|pm|a\.m\.|p\.m\.|o'?clock))", re.I)
_SKIP = re.compile(r"\?|\b(?:not|never|no|nothing|none|isn't|aren't|wasn't|weren't|doesn't|don't|didn't|won't|can't|cannot|couldn't|haven't|hasn't|"
                   r"if|would|could|shall|should|want|may|might|can|whether|unless|ago|yesterday|earlier|was|were|used\s+to|last\s+night|"
                   r"this\s+morning|usually|every\s+(?:night|day|evening|morning)|automatically|schedule[ds]?|automation)\b", re.I)
_FUTURE = re.compile(r"\b(?:will|'ll|going\s+to|shall)\b", re.I)
_PRONOUN = re.compile(r"\b(?:it|it's|its|they|they're|them|those|these|that's|both|all|everything|every\s+one)\b", re.I)
_LIGHT_WORD = re.compile(r"\b(?:lights?|lamps?|downlights?|spotlights?|lighting)\b", re.I)
_PCT = re.compile(r"\b(\d{1,3})\s*(?:%|percent|per\s*cent)", re.I)
# state words: (regex, meaning); "out"/"dark" are off for lights; "up"/"down" are open/closed for blinds
_ON = re.compile(r"\b(?:on|lit|running|active)\b", re.I)
_OFF = re.compile(r"\b(?:off|out|dark)\b", re.I)
_OPEN = re.compile(r"\b(?:open|opened|up|raised)\b", re.I)
_CLOSED = re.compile(r"\b(?:closed|shut|down|lowered)\b", re.I)
_SCENE_ON = re.compile(r"\b(?:on|running|active|set|going|activated|started)\b", re.I)


def _n(s: str) -> str:
    s = re.sub(r"\([^)]*\)", " ", (s or '').lower().replace('’', "'"))
    s = re.sub(r"(?<=\w)'s\b", " is", s)            # "Sunroom blind's down", "Good Night's running", "it's"
    s = re.sub(r"(?<=\w)'re\b", " are", s)
    s = re.sub(r"(?<=\w)'ll\b", " will", s)
    s = re.sub(r"[^a-z0-9%' ]+", " ", s)
    s = re.sub(r"\b(lights?|lamps?|blinds?|downlights?|spotlights?)\b", lambda m: m.group(1).rstrip('s'), s)
    s = re.sub(r"\blounge(?: room)?\b", "family room", s) if 'family room' in s or 'lounge' in s else s
    return re.sub(r"\s+", " ", s).strip()


def names(handles: dict) -> list[tuple[str, str]]:
    """(normalised name, handle), longest first: each enabled handle's label and handle words, a room light group's room words with a light
    word, a blind's own words with 'blind', a scene's label (and its spoken forms)."""
    from .core import SCENE_SAY as _SCENE_SAY  # noqa: PLC0415
    out = {}
    blinds = {h: t for h, t in handles.items() if t.get('kind') == 'blind' and t.get('enabled', True)}
    for h, t in handles.items():
        if not t.get('enabled', True) or t.get('kind') not in ('light', 'blind', 'scene'):
            continue
        ns = {_n(t['label']), _n(h.replace('_', ' '))}
        if t['kind'] == 'scene':
            ns |= _SCENE_SAY.get(_n(t['label']), set())
        if t['kind'] == 'blind' and len(t.get('entity_ids') or []) == 1:
            own = set(re.findall(r"[a-z]+", t['label'].lower())) - {'blind', 'blinds'}
            other = {w for o, ot in blinds.items() if o != h and len(ot.get('entity_ids') or []) == 1 for w in re.findall(r"[a-z]+", ot['label'].lower())}
            for w in own - other:
                ns.add(f'{w} blind')
        for n in ns:
            if n:
                out.setdefault(n, h)
    return sorted(out.items(), key=lambda x: -len(x[0]))


def spans(text: str, nm: list[tuple[str, str]]) -> tuple[str, list[tuple[int, int, str]]]:
    """(normalised text, [(start, end, handle)] in order): every name found, longest first, never overlapping."""
    s = f" {_n(text)} "
    taken, out = [False] * len(s), []
    for n, h in nm:
        for m in re.finditer(r"(?<= )" + re.escape(n) + r"(?= )", s):
            if not any(taken[m.start():m.end()]):
                out.append((m.start(), m.end(), h))
                for i in range(m.start(), m.end()):
                    taken[i] = True
    return s, sorted(out)


def mentioned(text: str, nm: list[tuple[str, str]]) -> list[str]:
    return list(dict.fromkeys(h for _a, _b, h in spans(text, nm)[1]))


def _light_truth(word: str, ents: list, states: dict, pct: int | None) -> bool | None:
    st = [states.get(e) for e in ents]
    st = [s for s in st if s and s.get('state') not in ('unavailable', 'unknown')]
    if not st:
        return None
    on = [s for s in st if s['state'] == 'on']
    if word == 'off':
        return not on
    if word == 'on' and pct is None:
        return bool(on)
    if pct is not None:
        if not on:
            return False
        return all(abs(round((s.get('attributes') or {}).get('brightness') or 0) / 2.55 - pct) <= 2.5 for s in on)
    return None


def _blind_truth(word: str, ents: list, states: dict, pct: int | None) -> bool | None:
    pos = []
    for e in ents:
        s = states.get(e)
        if not s or s.get('state') in ('unavailable', 'unknown'):
            return None
        p = (s.get('attributes') or {}).get('current_position')
        pos.append(p if p is not None else (100 if s['state'] == 'open' else 0))
    if pct is not None:
        return all(abs(p - pct) <= 3 for p in pos)
    if word == 'closed':
        return all(p <= 3 for p in pos)
    if word == 'open':
        return any(p > 3 for p in pos)
    return None


def _scene_truth(t: dict, states: dict) -> bool | None:
    from .core import _light_match  # noqa: PLC0415
    exp = t.get('expect') or {}
    if not exp:
        return None
    return all(_light_match(w)({'entity_id': e, **states[e]} if states.get(e) else None) for e, w in exp.items())


def check(reply: str, handles: dict, states: dict, pending: list, person_text: str = '', results: list | None = None,
          before: dict | None = None) -> tuple[str, list[str]]:
    """(reply, ['state'|'timer' per false clause]). The reply comes back unchanged when nothing in it is false. before: the states at the
    start of the turn, for "dimmer" / "brighter" / "already"."""
    from .core import _CLAUSE, _LEAD, _sentences  # noqa: PLC0415
    nm = names(handles)
    acted = [a.get('target_handle') or a.get('recipe_handle') for n, a, r in (results or []) if n in ('atlas_lights', 'atlas_blind', 'atlas_scene', 'atlas_schedule')]
    acted = [h for h in dict.fromkeys(acted) if h in handles]
    said = mentioned(person_text, nm)
    keep, bad = [], []
    for s in _sentences(reply):
        parts, dropped = [], False
        for c in [c for c in _CLAUSE.split(s) if c and c.strip()]:
            why = _false(c, s, handles, states, pending, nm, acted, said, before or {})
            if why:
                bad.append(why)
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
    return ' '.join(keep).strip(), bad


def _word(kind: str, text: str) -> str | None:
    if kind == 'light':
        m = [(x.start(), w) for rx, w in ((_OFF, 'off'), (_ON, 'on')) for x in rx.finditer(text)]
    elif kind == 'blind':
        m = [(x.start(), w) for rx, w in ((_CLOSED, 'closed'), (_OPEN, 'open')) for x in rx.finditer(text)]
    else:
        m = [(x.start(), 'on') for x in _SCENE_ON.finditer(text)]
    return m


_SO = re.compile(r",?\s+(?:so|because|as)\s+(?=I\b)", re.I)
_ALREADY = re.compile(r"\balready\b", re.I)
_WAS_ALREADY = re.compile(r"\b(?:was|were)\s+already\b", re.I)
_ALL_BLINDS = re.compile(r"\b(?:all\s+(?:of\s+)?the\s+blinds|every\s+blind|all\s+three\s+blinds|(?:the\s+)?blinds\s+are\s+all)\b", re.I)
_DARK = re.compile(r"\b(?:dark|lit\s+up)\b", re.I)
_DIMMER = re.compile(r"\b(?:dimmer|dimmed|darker|lower)\b", re.I)
_BRIGHTER = re.compile(r"\b(?:brighter|brightened|brighten|higher)\b", re.I)


def _step_truth(rel: str, ents: list, before: dict, states: dict) -> bool | None:
    """'dimmer' is true when some light is on and lower than at the start of the turn; 'brighter' when some light is higher, or came on."""
    def pct(s):
        return round(((s or {}).get('attributes') or {}).get('brightness') or 0) / 2.55 if (s or {}).get('state') == 'on' else 0
    seen = [(before.get(e), states.get(e)) for e in ents if before.get(e) and states.get(e)]
    if not seen:
        return None
    if rel == 'dim':
        return any(a.get('state') == 'on' and pct(a) < pct(b) - 1 for b, a in seen)
    return any(pct(a) > pct(b) + 1 for b, a in seen)


_IDIOM = re.compile(r"\bno\s+(?:worries|dramas|probs|problem|trouble|need)\b", re.I)


def _false(c: str, sentence: str, handles, states, pending, nm, acted, said, before) -> str | None:
    c = _SO.split(c)[0]                              # "The office light was already off, so I didn't change anything": the state is the first part
    already = bool(_ALREADY.search(c))
    if _SKIP.search(_IDIOM.sub(' ', _WAS_ALREADY.sub(' already ', c) if already else c)) or '?' in sentence:
        return None
    s, sp = spans(c, nm)
    if not sp and _ALL_BLINDS.search(c):            # "All the blinds are closed", "every blind": every enabled blind
        sp = [(0, len(s), h) for h, t in handles.items() if t.get('kind') == 'blind' and t.get('enabled', True) and len(t.get('entity_ids') or []) == 1]
    if not sp and _DARK.search(c):                  # "The office is dark now"
        areas = {(t.get('area') or '').lower(): h for h, t in handles.items() if t.get('kind') == 'light' and t.get('area') and h.endswith('_lights')}
        sp = [(0, len(s), h) for a, h in areas.items() if a and re.search(r"\b" + re.escape(a) + r"\b", s)][:1]
    if not sp and already:                          # "Already off!": what this turn acted on, or the one thing the person named
        sp = [(0, len(s), h) for h in (acted or (said if len(said) == 1 else []))]
    if not sp and _LIGHT_WORD.search(c):           # "Lights off in the office!": a room's lights by its area
        areas = {(t.get('area') or '').lower(): h for h, t in handles.items() if t.get('kind') == 'light' and t.get('area') and h.endswith('_lights')}
        sp = [(0, len(s), h) for a, h in areas.items() if a and re.search(r"\b" + re.escape(a) + r"\b", s)][:1]
    if not sp and _PRONOUN.search(c):
        hs = acted or (said if len(said) == 1 else [])
        sp = [(0, len(s), h) for h in hs]
    if not sp:
        return None
    timer = TIME.search(c)
    if _FUTURE.search(c) and not timer:
        return None                                  # an offer or a promise with no time: the claim guard reads those
    whole = len(sp) == 1 or all(a == 0 for a, _b, _h in sp)
    for i, (a, b, h) in enumerate(sp):
        t = handles[h]
        k = t['kind']
        if whole:
            near = s
        else:                                        # this mention's own words: after it up to the next mention, else the words just before it
            nxt = sp[i + 1][0] if i + 1 < len(sp) else len(s)
            prv = sp[i - 1][1] if i > 0 else 0
            after, before = s[b:nxt], s[prv:a]
            near = after if _word(k, after) or _PCT.search(after) else before
        ws = _word(k, near)
        word = (ws[0][1] if near is not s or len(ws) < 2 else (ws[-1][1] if len({w for _p, w in ws}) == 1 else None)) if ws else None
        pm = _PCT.search(near)
        pct = int(pm.group(1)) if pm else None
        if timer:
            op = {'off': 'off', 'closed': 'close', 'open': 'open', 'on': 'on'}.get(word) if word else None
            if op is None or (k == 'scene' and op != 'on'):
                continue
            if not any(p.get('handle') == h or set(handles.get(p.get('handle'), {}).get('entity_ids') or []) & set(t.get('entity_ids') or []) for p in pending):
                return 'timer'
            continue
        if k == 'scene':
            if word and _scene_truth(t, states) is False:
                return 'state'
        elif k == 'light':
            if (word or pct is not None) and _light_truth(word or 'on', t['entity_ids'], states, pct) is False:
                return 'state'
            rel = 'dim' if _DIMMER.search(near) else 'bright' if _BRIGHTER.search(near) else None
            if rel and before and _step_truth(rel, t['entity_ids'], before, states) is False:
                return 'state'
        elif k == 'blind':
            if (word or pct is not None) and _blind_truth(word, t['entity_ids'], states, pct) is False:
                return 'state'
    return None
