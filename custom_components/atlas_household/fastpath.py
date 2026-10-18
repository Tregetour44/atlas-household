"""Deterministic timer path (the lead project 18 Oct 21:4x, for the owner's timer priority): a strict grammar for

    "<turn|switch> [the] <target> <on|off> in <N> <minutes|hours>"     "<target> <on|off> at <time>"
    "<turn|switch> <on|off> [the] <target> in ..."                     "in <N> <unit>[,] turn [the] <target> <on|off>"
    "<run|start|activate|set> [the] <scene> [scene] in ... | at ..."

Only a whole-utterance match counts, and only when the target names exactly ONE enabled light or scene handle (by its label, without any
bracketed note, singular or plural). Then the guarded agent calls the coordinator's atlas_schedule itself, never through the model, so
every coordinator check stays: allowed targets, the whole-turn never-list (on the person's own words), the 24-hour cap, read-back, log and
undo. Anything else returns None and the turn goes to the model as before. Blinds and media are not on this path (lights and scenes first).
A bare clock time is its NEXT occurrence: "at 11" after midday is 11 pm; "at 8" at 9 am is 8 pm. Pure Python (no HA imports).
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
    elif h <= 12:
        # a bare hour: its next occurrence (h or h+12), so "at 11" after midday is 11 pm [the lead project]
        cands = sorted({h % 12, h % 12 + 12})
        nowm = now.hour * 60 + now.minute
        later = [c for c in cands if c * 60 + mi > nowm]
        h = later[0] if later else cands[0]
    return f'{h:02d}:{mi:02d}'


def parse_timer(text: str, handles: dict, now_local: datetime) -> dict | None:
    """atlas_schedule args for a strict timer request naming exactly one light or scene handle, else None."""
    text = (text or '').strip()
    if not text or len(text) > 200:
        return None
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
