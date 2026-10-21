"""Read-only fast answers (cloud robustness job, 21 Oct): a strict whole-utterance question about a reading the map lists ("what's the battery
at?", "how warm is it inside?", "what's the temp?", "how warm is the attic?") is answered from Home Assistant's state, without the model.
Pure Python (no HA import); nothing here can act: it only reads states through the backend's get_state.

The map's optional "readings" section (read-only domains only: sensor, weather, binary_sensor; never a handle, never offered to the model):
    "readings": {"battery": {"entity_id": "sensor.home_battery_soc"},
                 "outside": {"entity_id": "weather.home"},
                 "inside":  [{"entity_id": "sensor.loft_temperature", "name": "the loft"}, {"entity_id": "sensor.bedroom_temperature", "name": "the master bedroom"}]}
A reading that isn't listed is never answered here (the model answers from the prompt's readings), and so is any other wording: a forecast
("tomorrow"), advice ("should I run the AC"), a judgement ("is it hot?"), a second request, a credit question (no credit card exists yet).
"""
from __future__ import annotations

import re

READ_DOMAINS = ('sensor', 'weather', 'binary_sensor')
_CURLY = str.maketrans({'’': "'", '‘': "'", 'ʼ': "'"})
_LEAD = r"^(?:(?:hey|ok|okay)\s+)?(?:atlas\s+)?(?:(?:so|and|right|ok|okay)\s+)?(?:(?:can|could)\s+you\s+tell\s+me\s+|tell\s+me\s+)?"
_TAIL = r"(?:\s+(?:please|thanks|atlas|now|right\s+now|at\s+the\s+moment|mate))*$"
_WHATS = r"(?:what\s*s|what\s+is|whats)"
_HOWS = r"(?:how\s*s|how\s+is|hows)"
_BATTERY = r"(?:the\s+)?(?:home\s+|house\s+)?battery"
QUESTIONS = {
    'battery': [
        _WHATS + r"\s+" + _BATTERY + r"(?:\s+(?:charge|level|percentage))?(?:\s+(?:at|on|sitting\s+at))?",
        _HOWS + r"\s+" + _BATTERY + r"(?:\s+(?:going|holding\s+up|doing|looking|charge|level))?",
        r"how\s+(?:full|charged)\s+is\s+" + _BATTERY, r"where\s*s\s+" + _BATTERY + r"\s+at", r"what\s+percentage\s+is\s+" + _BATTERY,
        _BATTERY + r"(?:\s+(?:level|charge|percentage))?", r"how\s+much\s+(?:charge\s+is\s+in|charge\s+is\s+left\s+in)\s+" + _BATTERY,
        r"how\s+much\s+battery\s+(?:have\s+we\s+got|do\s+we\s+have|is\s+left)", r"(?:the\s+)?battery\s+(?:level|charge|percentage)",
    ],
    'inside': [
        r"how\s+(?:warm|hot|cold)\s+is\s+it\s+(?:inside|indoors|in\s+the\s+house|in\s+here)", r"how\s+(?:warm|hot|cold)\s+is\s+the\s+house",
        _WHATS + r"\s+the\s+(?:temperature|temp)\s+(?:inside|indoors|in\s+the\s+house|in\s+here)", r"(?:the\s+)?inside\s+(?:temperature|temp)",
        _WHATS + r"\s+the\s+inside\s+(?:temperature|temp)", r"what\s+temperature\s+is\s+it\s+(?:inside|indoors)",
    ],
    'outside': [
        _WHATS + r"\s+the\s+(?:temperature|temp)(?:\s+(?:outside|out\s+there|outdoors))?", r"how\s+(?:hot|warm|cold)\s+is\s+it\s+(?:outside|out\s+there|outdoors|out)",
        r"(?:the\s+)?(?:outside|outdoor)\s+(?:temperature|temp)", r"(?:temperature|temp)\s+outside", _WHATS + r"\s+the\s+weather(?:\s+(?:doing|like))?(?:\s+outside)?",
        _HOWS + r"\s+the\s+weather(?:\s+(?:looking|outside))?", r"what\s+temperature\s+is\s+it(?:\s+outside)?",
    ],
}
_COMPILED = {k: [re.compile(_LEAD + rx + _TAIL) for rx in v] for k, v in QUESTIONS.items()}
_ROOM = [r"how\s+(?:warm|hot|cold)\s+is\s+(?:it\s+in\s+)?(?P<r>[a-z ]+?)", _WHATS + r"\s+the\s+(?:temperature|temp)\s+in\s+(?P<r>[a-z ]+?)",
         r"(?P<r>[a-z ]+?)\s+(?:temperature|temp)", r"what\s+temperature\s+is\s+it\s+in\s+(?P<r>[a-z ]+?)"]
_ROOM_RX = [re.compile(_LEAD + rx + _TAIL) for rx in _ROOM]
_NOT = re.compile(r"\b(?:tomorrow|tonight|later|forecast|will|going\s+to|should|yesterday|today|week|last|why|and|then|but|or|if|charging|"
                  r"discharging|export\w*|solar|last\s+night|change|set|turn|switch|charge\s+it)\b")
WEATHER_WORDS = {'clear-night': 'clear', 'cloudy': 'cloudy', 'exceptional': 'unusual', 'fog': 'foggy', 'hail': 'hailing', 'lightning': 'stormy',
                 'lightning-rainy': 'stormy with rain', 'partlycloudy': 'partly cloudy', 'pouring': 'pouring', 'rainy': 'raining', 'snowy': 'snowing',
                 'snowy-rainy': 'sleeting', 'sunny': 'sunny', 'windy': 'windy', 'windy-variant': 'windy and cloudy'}


def check_readings(cfg) -> dict:
    """The map's readings section, validated: read-only domains only, each with an entity id (and a name for an inside room)."""
    if not cfg:
        return {}
    if not isinstance(cfg, dict) or set(cfg) - {'battery', 'outside', 'inside'}:
        raise ValueError('readings: only battery, outside and inside are supported')
    out = {}
    for k, v in cfg.items():
        items = v if isinstance(v, list) else [v]
        for it in items:
            e = str((it or {}).get('entity_id') or '')
            if e.split('.')[0] not in READ_DOMAINS:
                raise ValueError(f'readings.{k}: {e!r} is not a read-only reading')
            if k == 'inside' and not it.get('name'):
                raise ValueError('readings.inside: each room needs a name')
            if k == 'outside' and not e.startswith('weather.'):
                raise ValueError('readings.outside: a weather entity')
        out[k] = [dict(x) for x in items] if k == 'inside' else dict(v)
    return out


def _plain(text: str) -> str:
    s = (text or '').translate(_CURLY).lower().strip()
    s = re.sub(r"[^a-z0-9 ]+", " ", s.replace("'", ''))
    return re.sub(r"\s+", " ", s).strip()


def _room_key(name: str) -> str:
    return re.sub(r"^(?:the|my|our)\s+", "", _plain(name))


def parse_question(text: str, readings: dict) -> tuple[str, str | None] | None:
    """(key, room) for a strict whole-utterance question about a listed reading, else None."""
    if not readings or not text or len(text) > 90:
        return None
    s = _plain(text)
    if _NOT.search(s):
        return None
    for k, rxs in _COMPILED.items():
        if k in readings and any(rx.fullmatch(s) for rx in rxs):
            return k, None
    rooms = {_room_key(x['name']): x['name'] for x in readings.get('inside') or []}
    for rx in _ROOM_RX:
        m = rx.fullmatch(s)
        if m and _room_key(m.group('r')) in rooms:
            return 'room', rooms[_room_key(m.group('r'))]
    return None


def _num(v) -> str | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return str(int(f)) if f == int(f) else f'{round(f, 1)}'


async def answer(key: str, room: str | None, readings: dict, get_state) -> str:
    """The spoken answer from fresh states. A reading that is missing or unavailable is said so, never guessed."""
    async def val(e):
        st = await get_state(e)
        return None if st is None or st.get('state') in (None, '', 'unavailable', 'unknown') else st
    if key == 'battery':
        st = await val(readings['battery']['entity_id'])
        n = _num(st['state']) if st else None
        return f"The home battery is at {n}%." if n is not None else "The battery reading isn't available right now."
    if key == 'outside':
        st = await val(readings['outside']['entity_id'])
        if st is None:
            return "The weather reading isn't available right now."
        t = _num((st.get('attributes') or {}).get('temperature'))
        cond = WEATHER_WORDS.get(st['state'], str(st['state']).replace('-', ' '))
        return f"It's {t} degrees outside and {cond}." if t is not None else f"Outside it's {cond}; the temperature isn't available right now."
    rows = [x for x in readings.get('inside') or [] if key == 'inside' or x['name'] == room]
    said = []
    for x in rows:
        st = await val(x['entity_id'])
        n = _num(st['state']) if st else None
        said.append(f"{x['name']} is {n} degrees" if n is not None else f"{x['name']} isn't available right now")
    if not said:
        return "That reading isn't available right now."
    text = said[0] if len(said) == 1 else ', '.join(said[:-1]) + ' and ' + said[-1]
    text = text[:1].upper() + text[1:] if key == 'room' else 'Inside, ' + text
    return text + '.'
