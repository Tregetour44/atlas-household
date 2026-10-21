"""Deterministic paths. The TIMER path (the lead project 18 Oct 21:4x, for the owner's timer priority): a strict grammar for

    "<turn|switch> [the] <target> <on|off> in <N> <minutes|hours>"     "<target> <on|off> at <time>"
    "<turn|switch> <on|off> [the] <target> in ..."                     "in <N> <unit>[,] turn [the] <target> <on|off>"
    "<run|start|activate|set> [the] <scene> [scene] in ... | at ..."

Only a whole-utterance match counts, and only when the target names exactly ONE enabled light or scene handle (by its label, without any
bracketed note, singular or plural). Then the guarded agent calls the coordinator's atlas_schedule itself, never through the model, so
every coordinator check stays: allowed targets, the whole-turn never-list (on the person's own words), the 24-hour cap, read-back, log and
undo. Anything else returns None and the turn goes to the model as before. Blinds and media are not on this path (lights and scenes first).
A bare clock time is its NEXT occurrence: "at 11" after midday is 11 pm; "at 8" at 9 am is 8 pm. Pure Python (no HA imports).

The LEVEL path (R18; the Atlas-side project 19 Oct 00:0x, for the lights phase: Gemma doesn't reliably turn level words into numbers): a whole utterance
naming exactly ONE enabled light handle (a light, a room or a floor) plus a level or on/off, sent as atlas_lights by the coordinator itself:
    full / max / maximum / all the way (up) / crank (up) -> 100 (the owner: "crank" = full); half / halfway -> 50;
    right down / low / as low as possible / as low as it goes / dim as possible -> 20; "N%" / "N percent" -> N (1-100);
    turn / switch / pop ... on|off, kill ... -> on / off.
"crank it up a bit", any "a bit / a little / slightly", any question, any time word: not this path (the model handles them).
level_from_words(text) gives the same level from anywhere in the person's words, for a model call of brightness with no number.
"""
from __future__ import annotations

import re
from datetime import datetime

_NUM = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'eleven': 11, 'twelve': 12, 'fifteen': 15, 'twenty': 20, 'twenty five': 25, 'thirty': 30, 'forty': 40, 'forty five': 45, 'fifty': 50,
        'sixty': 60, 'ninety': 90}
_UNIT = r"(minutes?|mins?|hours?|hrs?)"
_N = r"(\d{1,4}|" + "|".join(sorted(_NUM, key=len, reverse=True)) + r")"
_DUR = r"\bin\s+(?:(half an hour|half an hr)|" + _N + r"\s+" + _UNIT + r"(?:\s+and a half)?)"
_TIME = r"\bat\s+(noon|midday|midnight|\d{1,2}(?:[:.]\d{2})?(?:\s*(?:am|pm|a\.m\.|p\.m\.))?)"
_WHEN = r"(?:" + _DUR + r"|" + _TIME + r")"
_LEAD = r"^(?:(?:hey\s+)?atlas,?\s+)?(?:please\s+|can you\s+|could you\s+|would you\s+)?"
_TAIL = r"(?:\s+please)?\s*[.!]?\s*$"          # no "?": "porch lights on at 7?" is a question [B16-03]
_FORMS = [
    re.compile(_LEAD + r"(?:turn|switch)\s+(?:the\s+)?(?P<t>.+?)\s+(?P<op>on|off)\s+" + _WHEN + _TAIL, re.I),
    re.compile(_LEAD + r"(?:turn|switch)\s+(?P<op>on|off)\s+(?:the\s+)?(?P<t>.+?)\s+" + _WHEN + _TAIL, re.I),
    re.compile(_LEAD + r"(?:the\s+)?(?P<t>.+?)\s+(?P<op>on|off)\s+" + _WHEN + _TAIL, re.I),
    re.compile(_LEAD + _WHEN + r",?\s+(?:turn|switch)\s+(?:the\s+)?(?P<t>.+?)\s+(?P<op>on|off)" + _TAIL, re.I),
    re.compile(_LEAD + _WHEN + r",?\s+(?:turn|switch)\s+(?P<op>on|off)\s+(?:the\s+)?(?P<t>.+?)" + _TAIL, re.I),
    re.compile(_LEAD + r"(?P<scene_verb>run|start|activate|set|put on)\s+(?:the\s+)?(?P<t>.+?)(?:\s+scene)?\s+" + _WHEN + _TAIL, re.I),
]


def _norm(s: str) -> str:
    s = re.sub(r"\([^)]*\)", " ", s.lower())
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\b(lights?|lamps?)\b", lambda m: m.group(1).rstrip('s'), s)      # singular and plural alike
    s = re.sub(r"\blounge(?: room)?\b", "living room", s)                       # "lounge" is a common word for the living room
    return re.sub(r"\s+", " ", s).strip()


def _targets(handles: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for h, t in handles.items():
        if t.get('enabled') and t.get('kind') in ('light', 'scene'):
            names = {_norm(t['label']), _norm(h.replace('_', ' '))}
            note = re.search(r"\(([A-Za-z]+)\)", t['label'])
            if note:                                   # "Ground floor (downstairs) lights" is also "downstairs lights"
                names.add(_norm(re.sub(r"^[^(]*\([^)]*\)", note.group(1), t['label'])))
            for name in names:
                out.setdefault(name, []).append(h)
    return out


def _minutes(m: re.Match) -> int | None:
    """m is a match of _DUR: group 1 'half an hour', group 2 the number, group 3 the unit."""
    if m.group(1):
        return 30
    n = int(m.group(2)) if m.group(2).isdigit() else _NUM.get(m.group(2).lower())
    if n is None:
        return None
    hours = m.group(3).lower().startswith('h')
    if 'and a half' in m.group(0).lower() and not hours:
        return None                                   # "10 minutes and a half": not in the grammar, the model handles it [B16-04]
    return n * 60 + (30 if hours and 'and a half' in m.group(0).lower() else 0) if hours else n


def _clock(spec: str, now: datetime) -> str | None:
    s = spec.lower().replace('.', ':').replace(' ', '')
    if s in ('noon', 'midday'):
        return '12:00'
    if s == 'midnight':
        return '00:00'
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?(am|pm|a:m:|p:m:)?", s)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or '').replace(':', '')
    if mi > 59 or h > 23 or (ap and not 1 <= h <= 12):
        return None
    if ap:
        h = (h % 12) + (12 if ap == 'pm' else 0)
    elif m.group(1).startswith('0'):
        pass                                          # "04:00", "00:30", "0:15": a 24-hour time as written, never flipped to pm [cloud review 2]
    elif h <= 12:
        # a bare hour: its next occurrence (h or h+12), so "at 11" after midday is 11 pm [the lead project]
        cands = sorted({h % 12, h % 12 + 12})
        nowm = now.hour * 60 + now.minute
        later = [c for c in cands if c * 60 + mi > nowm]
        h = later[0] if later else cands[0]
    return f'{h:02d}:{mi:02d}'


def parse_timer(text: str, handles: dict, now_local: datetime, scenes: bool = True) -> dict | None:
    """atlas_schedule args for a strict timer request naming exactly one light or scene handle, else None."""
    text = (text or '').strip()
    if not text or len(text) > 200:
        return None
    if not scenes:
        handles = {h: t for h, t in handles.items() if t.get('kind') != 'scene'}     # a map without scene timers [P2-04]
    names = _targets(handles)
    for rx in _FORMS:
        m = rx.match(text)
        if not m:
            continue
        hs = names.get(_norm(m.group('t')))
        if not hs or len(set(hs)) != 1:
            return None                               # unknown or ambiguous target: the model handles it
        h = hs[0]
        kind = handles[h]['kind']
        scene_form = 'scene_verb' in m.groupdict() and m.group('scene_verb')
        if (kind == 'scene') != bool(scene_form):
            return None                               # "turn the Relax scene on" / "run the study lights": not this path
        op = 'on' if kind == 'scene' else m.group('op').lower()
        whole = m.group(0)
        tm = re.search(_TIME, whole, re.I)
        dm = re.search(_DUR, whole, re.I)
        if dm:
            mins = _minutes(dm)
            if not mins or mins > 1440:
                return None
            return {'target_handle': h, 'operation': op, 'in_minutes': mins}
        if tm:
            at = _clock(tm.group(1), now_local)
            return {'target_handle': h, 'operation': op, 'at_time': at} if at else None
        return None
    return None


_LVL_WORDS = [
    (100, r"(?:full(?:\s+brightness)?|max(?:imum)?(?:\s+brightness)?|all\s+the\s+way(?:\s+up)?|as\s+bright\s+as\s+(?:possible|it\s+goes))"),
    (50, r"(?:half(?:\s+brightness)?|halfway|half\s+way)"),
    (20, r"(?:right\s+down|low|as\s+low\s+as\s+(?:possible|it\s+goes)|(?:as\s+)?dim\s+as\s+(?:possible|it\s+goes))"),
]
_UNITS = ['one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']
_TEENS = ['ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen']
_TENS = ['twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']
_NUMW = (r"(?:(?:one|a)\s+hundred|hundred|(?:" + "|".join(_TENS) + r")(?:[\s-](?:" + "|".join(_UNITS) + r"))?|"
         + "|".join(_TEENS) + "|" + "|".join(_UNITS) + r")")                 # spoken numbers 1-100 (C0h H11: "thirty percent")


def _num(s: str) -> int | None:
    """'30' / 'thirty' / 'seventy-five' / 'a hundred' -> int, else None (an exact word list, never a guess)."""
    s = re.sub(r"[\s-]+", " ", (s or '').strip().lower())
    if s.isdigit():
        return int(s)
    if s in ('hundred', 'a hundred', 'one hundred'):
        return 100
    words = s.split()
    if len(words) == 1 and words[0] in _UNITS:
        return _UNITS.index(words[0]) + 1
    if len(words) == 1 and words[0] in _TEENS:
        return _TEENS.index(words[0]) + 10
    if words and words[0] in _TENS and (len(words) == 1 or (len(words) == 2 and words[1] in _UNITS)):
        return (_TENS.index(words[0]) + 2) * 10 + (_UNITS.index(words[1]) + 1 if len(words) == 2 else 0)
    return None


_PCT = r"(?P<pct>\d{1,3}|" + _NUMW + r")\s*(?:%|percent|per\s+cent)"
_LVL = r"(?:(?:on\s+)?(?:to|at|on)\s+)?(?:" + _PCT + "|" + "|".join(f"(?P<l{n}>{rx})" for n, rx in _LVL_WORDS) + r")"
_SOFT = re.compile(r"\b(a\s+bit|a\s+little|slightly|a\s+touch|bit\s+more|bit\s+less|tad)\b|\?", re.I)
_LEVEL_FORMS = [
    re.compile(_LEAD + r"(?:set|turn|put|take|bring|switch|make|dim|crank|chuck|pop|flick)\s+(?:up\s+|down\s+)?(?:the\s+)?(?P<t>.+?)\s+(?:up\s+|down\s+)?" + _LVL + _TAIL, re.I),
    re.compile(_LEAD + r"(?:the\s+)?(?P<t>.+?)\s+(?:up\s+|down\s+)?" + _LVL + _TAIL, re.I),
    re.compile(_LEAD + r"crank\s+(?:up\s+)?(?:the\s+)?(?P<t>.+?)(?:\s+up)?" + _TAIL, re.I),                       # "crank the study lights (up)"
]
_ONOFF_FORMS = [
    re.compile(_LEAD + r"(?:turn|switch|pop|flick|put)\s+(?:the\s+)?(?P<t>.+?)\s+(?P<op>on|off)" + _TAIL, re.I),
    re.compile(_LEAD + r"(?:turn|switch|pop|flick|put)\s+(?P<op>on|off)\s+(?:the\s+)?(?P<t>.+?)" + _TAIL, re.I),
    re.compile(_LEAD + r"(?P<op>kill)\s+(?:the\s+)?(?P<t>.+?)" + _TAIL, re.I),
    re.compile(_LEAD + r"(?:the\s+)?(?P<t>.+?)\s+(?P<op>on|off)" + _TAIL, re.I),                                  # "downstairs lights off"
]
_TIMEWORD = re.compile(r"\b(in|at|after|for|until|till|tonight|tomorrow|later|minutes?|mins?|hours?|o'?clock|am|pm)\b", re.I)


_CURLY = str.maketrans({'\u2019': "'", '\u2018': "'", '\u02bc': "'"})     # typed smart apostrophes ("don’t") [R18b-02]
_RELATIVE = re.compile(r"\bby\s+\d|\b(?:up|down|dim|brighten|raise|lower|increase|decrease|reduce|boost)\b", re.I)
_PCT_TO = re.compile(r"\b(?:to|at)\s+(?:\d{1,3}|" + _NUMW + r")\s*(?:%|percent|per\s+cent)", re.I)
_WHEN_ANY = re.compile(r"\bin\s+(?:\d+|a|an|half|one|two|three|four|five|ten|fifteen|twenty|thirty|forty|fifty|sixty)\b[^.]{0,20}?\b(?:minutes?|mins?|hours?|hrs?)\b|"
                       r"\bat\s+\d{1,2}(?::\d\d)?\s*(?:am|pm|a\.m\.|p\.m\.)|\bat\s+(?:noon|midnight|midday)\b|\b\d{1,2}[:.]\d\d\b|"
                       r"\b(?:tonight|tomorrow|later|o'?clock|when|until|till|after)\b", re.I)


def _relative_pct(text: str) -> bool:
    """"up 10%", "down 20%", "dim it 30%", "by 10%": a change BY an amount, never a level; only "to/at N%" names the level [R18b-01]."""
    return bool(re.search(_PCT, text, re.I)) and (bool(re.search(r"\bby\s+(?:\d|" + _NUMW + r")", text, re.I)) or (bool(_RELATIVE.search(text)) and not _PCT_TO.search(text)))


def _level_of(m: re.Match) -> int | None:
    gd = m.groupdict()
    if gd.get('pct'):
        n = _num(gd['pct'])
        if n is None:
            return None
        return n if 1 <= n <= 100 else None
    for n, _rx in _LVL_WORDS:
        if gd.get(f'l{n}'):
            return n
    return None


def _one_light(names: dict, handles: dict, t: str) -> str | None:
    hs = names.get(_norm(t))
    if not hs or len(set(hs)) != 1 or handles[hs[0]]['kind'] != 'light':
        return None
    return hs[0]


_ASKING = re.compile(r"^\W*(?:(?:hey\s+)?atlas,?\s+)?(?:who|what|why|how|which|where|when|are|is|was|were|did|does|do|has|have|had|keep|leave|left|"
                     r"stay|stays|still|why's|what's|who's)\b", re.I)      # a question or a statement, said without "?" [R18d-02]; not "left"
# anywhere: four lights are named "... Left" [R18e-02]
_DOWN_ANY = re.compile(r"\b(down|dim|dimmer|lower|drop|reduce|darker|decrease|less)\b", re.I)
_UP_ANY = re.compile(r"\b(up|brighten|brighter|raise|increase|boost|crank\w*|more)\b", re.I)


def _level_ok(text: str, n: int, said_pct: bool) -> bool:
    """The whole sentence must agree with the level it names [R18d-01/02]: exactly one level in it; no word, the verb included, against a level
    word ("dim it to full", "crank down the lights", "brighten them low"); with "up"/"down" a level word needs "to" ("turn it down half" is a
    change, like "down 50%"); and never a question or a statement ("are the lights on full", "leave the lights at half")."""
    if _ASKING.search(text):
        return False
    levels = set()
    for m in _LVL_ANY.finditer(text):
        w = m.group(0).lower()
        pm = re.fullmatch(_PCT, w, re.I)
        levels.add(100 if w.startswith('crank') else _num(pm.group('pct')) if pm else next((k for k, rx in _LVL_WORDS if re.fullmatch(rx, w, re.I)), None))
    levels.discard(None)
    if 'crank' in text.lower():
        levels.discard(100)
        levels.add(100)
    if len(levels) > 1:
        return False
    if said_pct:
        return True                                      # a spoken "to N%" is what was said (relative "up N%" is refused before this)
    rest = _LVL_ANY.sub(' ', text)                       # the words around the level phrase ("right down", "all the way up" are levels)
    if (n > 50 and _DOWN_ANY.search(rest)) or (n < 50 and _UP_ANY.search(rest)):
        return False
    if n == 50 and (_DOWN_ANY.search(rest) or _UP_ANY.search(rest)) and not re.search(r"\b(?:to|at)\s+half", text, re.I):
        return False                                     # "turn it down half", "dim it half" are changes (like "down 50%"); "dim it to half" is a level [R18e-01]
    return True


def parse_level(text: str, handles: dict) -> dict | None:
    """atlas_lights args for a strict level or on/off request naming exactly one enabled light handle, else None (the model handles it)."""
    text = (text or '').translate(_CURLY).strip()
    if not text or len(text) > 160 or _SOFT.search(text) or _NEG.search(text) or _relative_pct(text):
        return None                                   # "don't turn the study lights off": never this path [R18-01]
    names = _targets(handles)
    for rx in _LEVEL_FORMS:
        m = rx.match(text)
        if not m:
            continue
        h = _one_light(names, handles, m.group('t'))
        if not h:
            continue
        lvl = _level_of(m) if 'pct' in m.groupdict() else 100      # the bare "crank the X" form is full [the owner]
        if lvl is None or not _level_ok(text, lvl, bool(m.groupdict().get('pct'))):
            return None
        return {'target_handle': h, 'operation': 'brightness', 'brightness_percent': lvl}
    if _TIMEWORD.search(text) or _ASKING.search(text):
        return None                                   # "turn the porch lights on at 7" is the timer path's or the model's; "are the porch lights on" asks
    for rx in _ONOFF_FORMS:
        m = rx.match(text)
        if not m:
            continue
        h = _one_light(names, handles, m.group('t'))
        if not h:
            continue
        return {'target_handle': h, 'operation': 'off' if m.group('op').lower() in ('off', 'kill') else 'on'}
    return None


_LVL_ANY = re.compile(r"\b(?:crank(?:ed|ing)?|" + _PCT + "|" + "|".join(rx for _n, rx in _LVL_WORDS) + r")(?![\w%])", re.I)   # whole words only:
# "lower" is not "low" [R18-01]
_NEG = re.compile(r"\b(not|never|no|too|don'?t|do not|isn'?t|aren'?t|won'?t|stop)\b", re.I)          # "not at full", "too low, turn them up"
_HALF_TIME = re.compile(r"\bhalf\s+(?:past|an?\b|hour)|\b(?:and a|an?) half\b|\bhalf\s+(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d)", re.I)
_DOWNWARD = re.compile(r"\b(down|lower|dim(?:mer)?|darker|less|reduce|drop)\b", re.I)
_UPWARD = re.compile(r"\b(up|raise|brighter|more|increase|boost)\b", re.I)


_OBJ = r"(?:it|them|that|those|these|(?:the\s+|all\s+the\s+)?(?:lights?|lamps?))"   # no free words: a named light is the fast path's [R18d-01]
_WORD_FORMS = [      # the WHOLE utterance, or no level: a whitelist, so a change word ("10% brighter", "drop it 30%") can never become a level [R18c-01]
    re.compile(_LEAD + r"(?:set|turn|put|take|bring|switch|make|dim|crank)\s+(?P<d1>up\s+|down\s+)?(?P<t>" + _OBJ + r")\s+(?P<d2>up\s+|down\s+)?" + _LVL + _TAIL, re.I),
    re.compile(_LEAD + r"(?P<t>" + _OBJ + r")\s+(?P<d2>up\s+|down\s+)?" + _LVL + _TAIL, re.I),
    re.compile(_LEAD + r"crank\s+(?:up\s+)?(?P<t>" + _OBJ + r")(?:\s+up)?" + _TAIL, re.I),        # "crank it (up)" = full [the owner]
    re.compile(_LEAD + _LVL + _TAIL, re.I),                                                    # the bare answer to "How bright?": "half", "40%"
]
_NEG_NT = re.compile(r"\w+n't\b|\bnot\b", re.I)                                              # "I didn't say full", "shouldn't be at 40%" [R18c-02]


def level_from_words(text: str) -> int | None:
    """The level the person's WHOLE utterance names, in one of the strict shapes "<verb> it|them|the … lights [up|down] [to] <level>",
    "the … lights [to] <level>", "crank it|them|the … lights [up]" (= 100) or a bare "<level>", else None, so the coordinator asks "How bright?".
    Never for soft words, negation, a time, a relative change ("up 10%", "10% brighter"), or a direction that disagrees with a level word
    ("crank it down", "turn it up low") [R18-01, R18b-01, R18c-01/02]."""
    text = (text or '').translate(_CURLY).strip()
    if (not text or len(text) > 120 or _SOFT.search(text.replace('?', '')) or _NEG.search(text) or _NEG_NT.search(text) or _HALF_TIME.search(text)
            or _relative_pct(text) or _WHEN_ANY.search(text) or re.search(r"\bat\s+\d{1,2}\b(?!\s*(?:%|percent|per\s+cent))", text, re.I)):
        return None
    for i, rx in enumerate(_WORD_FORMS):
        m = rx.match(text)
        if not m:
            continue
        gd = m.groupdict()
        n = 100 if i == 2 else _level_of(m)
        if n is None:
            return None
        return n if _level_ok(text, n, bool(gd.get('pct'))) else None
    return None


# ---------- the SCENE and BLIND paths (cloud robustness job, 21 Oct: faster replies for the phase-2 map) ----------
# A whole utterance naming exactly ONE enabled, reviewed scene ("good night", "run wind down", "let's wind down", "put good night on") is sent as
# atlas_scene; a whole utterance that only moves blinds ("close the sunroom blind", "family room blinds up", "all the blinds to 30%") is sent
# as atlas_blind, one call per handle, with the blinds taken ONLY from Coordinator._blind_scope (the which-blind rule, unchanged: unclear
# words return None and the model asks). Never for a question, a negation, a soft or relative change, a time, a number that isn't a
# percentage, or anything else in the turn; every coordinator check (never-list, scope, read-back, log, undo) runs as for a model call.
_SCENE_SAY = {'good night': {'good night', 'goodnight', 'good nite', 'night night', 'nighty night'}, 'wind down': {'wind down', 'winddown'}}
_FILL_LEAD = re.compile(r"^(?:(?:hey|ok|okay)\s+)?(?:atlas\s+)?(?:(?:ok|okay|right|alright|so)\s+)?(?:please\s+)?(?:(?:can|could|would)\s+you\s+(?:please\s+)?)?")
_FILL_TAIL = re.compile(r"(?:\s+(?:please|thanks|thank\s+you|cheers|mate|atlas|now|for\s+me))*$")
_SCENE_FORMS = [
    re.compile(r"^(?:(?:run|start|activate|do|set|put\s+on|turn\s+on|switch\s+on|put|begin|trigger)\s+)?(?:the\s+)?(?P<n>[a-z ]+?)(?:\s+(?:scene|mode))?(?:\s+on)?$"),
    re.compile(r"^(?:let\s?s|time\s+to|time\s+for)\s+(?:the\s+)?(?P<n>[a-z ]+?)(?:\s+(?:scene|mode))?$"),
    re.compile(r"^(?P<n>[a-z ]+?)\s+time$"),
]


def _plain(text: str) -> str:
    """Lower case, typed apostrophes folded, punctuation other than % dropped, "per cent"/"percent" as %, spaces collapsed."""
    s = (text or '').translate(_CURLY).lower().strip()
    s = re.sub(r"\s*(?:per\s*cent|percent)\b", "%", s)
    s = re.sub(r"[^a-z0-9% ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _scene_names(handles: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for h, t in handles.items():
        if t.get('kind') == 'scene' and t.get('enabled', True) and t.get('expect'):       # reviewed scenes only, as tools._enum offers them
            label = _norm(t['label'])
            names = {label, _norm(h.replace('_', ' '))} | _SCENE_SAY.get(label, set()) | {_norm(a) for a in t.get('aliases') or []}
            for n in names:
                out.setdefault(n, []).append(h)
    return out


def parse_scene(text: str, handles: dict) -> dict | None:
    """atlas_scene args for a whole utterance that names exactly one enabled, reviewed scene, else None (the model handles it)."""
    raw = (text or '').translate(_CURLY).strip()
    if not raw or len(raw) > 80 or '?' in raw or re.search(r"\d", raw) or _NEG.search(raw) or _NEG_NT.search(raw) or _WHEN_ANY.search(raw) \
            or _TIMEWORD.search(raw) or _ASKING.search(raw):
        return None
    s = _FILL_TAIL.sub('', _FILL_LEAD.sub('', _plain(raw))).strip()
    names = _scene_names(handles)
    for rx in _SCENE_FORMS:
        m = rx.match(s)
        if m:
            hs = names.get(m.group('n').strip())
            if hs and len(set(hs)) == 1:
                return {'recipe_handle': hs[0]}
    return None


_B_OBJ = (r"(?P<b>(?:(?:the|my|our|both|every|all(?:\s+of)?(?:\s+the)?|all\s+three|the\s+two)\s+)?(?:[a-z]+\s+){0,6}?(?:blinds?|ones?)"
          r"(?:\s+in\s+the\s+[a-z]+(?:\s+room)?)?)")      # "the blind in the sunroom", "the window blind in the family room"
_B_N = r"(?P<n>\d{1,3}|" + _NUMW + r")\s*%"
_BLIND_FORMS = [   # (pattern, operation); position when the pattern has <n> or 'half'
    (re.compile(r"^(?:close(?:\s+up)?|shut|lower|drop)\s+" + _B_OBJ + r"(?:\s+(?:down|closed|shut))?(?:\s+(?:fully|completely|all\s+the\s+way))?$"), 'close'),
    (re.compile(r"^(?:pull|put|bring|roll|let)\s+" + _B_OBJ + r"\s+down(?:\s+(?:fully|completely|all\s+the\s+way))?$"), 'close'),
    (re.compile(r"^(?:pull|put|bring|roll)\s+down\s+" + _B_OBJ + r"$"), 'close'),
    (re.compile(r"^get\s+" + _B_OBJ + r"\s+(?:closed|shut|down)$"), 'close'),
    (re.compile(r"^" + _B_OBJ + r"\s+(?:down|closed|shut)$"), 'close'),
    (re.compile(r"^(?:open(?:\s+up)?|raise|lift)\s+" + _B_OBJ + r"(?:\s+up)?(?:\s+(?:fully|completely|all\s+the\s+way))?$"), 'open'),
    (re.compile(r"^(?:pull|put|bring|roll)\s+" + _B_OBJ + r"\s+up(?:\s+(?:fully|completely|all\s+the\s+way))?$"), 'open'),
    (re.compile(r"^(?:pull|put|bring|roll)\s+up\s+" + _B_OBJ + r"$"), 'open'),
    (re.compile(r"^get\s+" + _B_OBJ + r"\s+open$"), 'open'),
    (re.compile(r"^" + _B_OBJ + r"\s+(?:up|open)$"), 'open'),
    (re.compile(r"^(?:(?:set|put|move|bring|take|open|close|lower|raise|make)\s+)?" + _B_OBJ + r"\s+(?:to|at)\s+" + _B_N + r"(?:\s+open)?$"), 'position'),
    (re.compile(r"^(?:(?:set|put|move|bring|take|make)\s+)?" + _B_OBJ + r"\s+" + _B_N + r"\s+open$"), 'position'),
    (re.compile(r"^(?:(?:set|put|move|bring|open|close|lower|raise)\s+)?" + _B_OBJ + r"\s+(?:to\s+)?(?P<half>half\s*way|half)(?:\s+(?:open|up|down|closed))?$"), 'position'),
]
_B_NOT = re.compile(r"\b(?:draw|drawn|bit|little|slightly|touch|tad|more|less|further|by|then|after|before|when|until|till|if|again|back|instead|light|lights|"
                    r"lamp|turn|switch|on|off|closed\s+\d|\d+\s*%\s+closed)\b")


def parse_blind(text: str, handles: dict, scope) -> list[dict] | None:
    """atlas_blind args (one per handle) for a whole utterance that only moves blinds, else None. scope(text) is Coordinator._blind_scope:
    the ONLY source of which blinds (None = unclear, so the model asks which). The handles are the fewest enabled blind handles covering
    exactly that scope (the pair handle for both family-room blinds)."""
    raw = (text or '').translate(_CURLY).strip()
    if not raw or len(raw) > 120 or '?' in raw or _NEG.search(raw) or _NEG_NT.search(raw) or _WHEN_ANY.search(raw) or _ASKING.search(raw) \
            or re.search(r"\bat\s+\d{1,2}\b(?!\s*(?:%|per\s*cent|percent))", raw, re.I):
        return None
    s = _FILL_TAIL.sub('', _FILL_LEAD.sub('', _plain(raw))).strip()
    s = re.sub(r"^(?:hey\s+)?atlas\s+", "", s)
    if _B_NOT.search(s) or re.search(r"\d", re.sub(_B_N, ' ', s)):
        return None                                   # a bare number that isn't a percentage (a time?), or any word outside the grammar
    for rx, op in _BLIND_FORMS:
        m = rx.match(s)
        if not m:
            continue
        b = m.group('b')
        if re.search(r"\b(?:open|close|shut|raise|lower|lift|up|down|set|put|pull|roll|get|half)\b", b):
            return None                               # a second movement inside the object: "close the sunroom and open the window blind"
        args = {'operation': op}
        if op == 'position':
            if m.groupdict().get('half'):
                n = 50
            else:
                n = _num(m.group('n'))
            if n is None or not 0 <= n <= 100:
                return None
            if n in (0, 100):
                args = {'operation': 'close' if n == 0 else 'open'}
            else:
                args['position_percent'] = n
        sc = scope(text)
        if not sc:
            return None                               # unclear which blind: the model asks [the which-blind rule]
        hs = _cover(sc, handles)
        if not hs:
            return None
        return [{'target_handle': h, **args} for h in hs]
    return None


def _cover(scope: set, handles: dict) -> list[str]:
    """The fewest enabled blind handles whose entities exactly cover scope (a handle never reaches outside it), else []."""
    left, out = set(scope), []
    blinds = sorted(((h, set(t.get('entity_ids') or [])) for h, t in handles.items() if t.get('kind') == 'blind' and t.get('enabled', True)),
                    key=lambda x: (-len(x[1]), x[0]))
    if left - {e for _h, es in blinds for e in es}:
        return []                                     # the words name a blind that isn't enabled: the model says so
    for h, es in blinds:
        if es and es <= left:
            out.append(h)
            left -= es
    return out if not left else []
