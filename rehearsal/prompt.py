"""The real go-live prompt (atlas-current/prompt-template.golive.jinja), rendered the way HA renders it, against SYNTHETIC readings and the
fixture house's live light and blind states, then joined with the coordinator's API prompt exactly as tools.system_prompt does.

Adaptation (documented, nothing else changed): the place lines name the live rooms, so they are mapped to the synthetic map's rooms with
fixture.LIVE_TO_SYNTHETIC; the example sensor ids get synthetic values (below); the light / blind id lists are the fixture's entities.
A minimal HA-like Jinja environment (states(), state_attr(), is_state(), area_name(), as_datetime, timedelta, now(), the 'match' and
'is_number' tests and float/int/is_number filters) renders it. Pure Python; no HA.
"""
from __future__ import annotations

import pathlib
import re
import sys
from datetime import datetime, timedelta

import jinja2

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fixture import ROOT, LIVE_TO_SYNTHETIC  # noqa: E402

TEMPLATE = ROOT / 'atlas-current' / 'prompt-template.golive.jinja'

PLACE_LINES = [   # the go-live prompt's place lines, live -> synthetic (exact replacements, applied before the word table)
    ('the Loft, Study and Guest Bedroom', 'the Attic, Office and Bedroom South'),
    ('the Living Room, Kitchen, Dining Room, Hallway, Atrium, Master Bedroom, Laundry and Garage', 'the Family Room, Galley, Corridor, Sunroom, Utility, Carport and Workshop'),
    ('"the porch light" means all the Porch lights.', '"the entry light" means all the Entry lights.'),
    ('the "pergola lights" are the Pergola floodlights and spotlights on the Patio; the "garden lights" are the Garden Spotlight and the Fountain Spotlight.',
     'the "garden lights" are the Yard Spot and the Flood Lamp on the Deck.'),
    ('There are two TVs: the Living Room TV and the Study TV.', 'There are two TVs: the Family Room TV and the TV Set.'),
    ('- "bedroom" on its own could be the Master or Guest Bedroom: ask which.\n', '- "bedroom" on its own means Bedroom South.\n'),
    ('"upstairs" = Loft, Study, Guest Bedroom; "downstairs" = Ground floor (Living Room, Kitchen, Dining Room, Hallway, Atrium, Master Bedroom, Laundry, Garage); "lounge" = Living Room; "outside" = Patio and Porch; "bedroom" alone = both the Master Bedroom and the Guest Bedroom: give both.',
     '"upstairs" = Attic, Office, Bedroom South; "downstairs" = Ground floor (Family Room, Galley, Corridor, Sunroom, Utility, Carport, Workshop); "lounge" = Family Room; "outside" = Deck and Entry; "bedroom" alone = Bedroom South.'),
    ('Garage temperature', 'Workshop temperature'), ('- Garage: high', '- Workshop: high'),
    ('Master bedroom (wardrobe)', 'Bedroom South (wardrobe)'),
]

LIGHT_AREAS = {}      # entity -> area, from the fixture map's single-light handles


def adapt(src: str, lights: list[str], covers: list[str]) -> str:
    for a, b in PLACE_LINES:
        if a not in src:
            raise ValueError(f'prompt line not found (template changed?): {a[:60]}')
        src = src.replace(a, b)
    for a, b in LIVE_TO_SYNTHETIC:
        src = re.sub(r'(?<![\w.])' + re.escape(a) + r'(?![\w])', b, src)
    src = re.sub(r'\{% for id in \["light\.example_40".*?\] %\}', '{% for id in ' + repr(lights).replace("'", '"') + ' %}', src, flags=re.S)
    src = src.replace('["cover.example_23","cover.example_106","cover.example_107"]', repr(covers).replace("'", '"'))
    src = src.replace("cover.example_23", covers[0])
    return src


READINGS = {   # synthetic values for the example sensor ids (an ordinary sunny spring evening)
    'sensor.example_01': '64', 'sensor.example_04': '0', 'sensor.example_05': '620', 'sensor.example_27': '0', 'sensor.example_28': '0',
    'sensor.example_36': '18.4', 'sensor.example_06': '9.2', 'sensor.example_09': '0.41', 'sensor.example_10': '3.1', 'sensor.example_08': '7.9',
    'sensor.example_07': '18.4',
    'weather.example_37': 'partlycloudy', 'sensor.example_11': '23.1', 'sensor.example_13': '18.9', 'sensor.example_12': '22.4', 'sensor.example_26': '26.0',
    'climate.example_17': 'off', 'todo.household_reminders': '2', 'binary_sensor.example_18': 'off', 'input_datetime.example_38': '2026-10-14',
    'binary_sensor.example_19': 'off', 'input_datetime.example_39': '2026-10-20',
    'input_text.example_03': 'Wed 21 Oct: partly cloudy, 27/16 °C, 0 mm; Thu 22 Oct: showers, 22/15 °C, 6 mm; Fri 23 Oct: sunny, 25/14 °C, 0 mm',
    'input_text.example_30': '22:00 clear 19 °C; 01:00 clear 17 °C; 04:00 clear 16 °C; 07:00 cloudy 18 °C; 10:00 showers 20 °C; 13:00 showers 21 °C',
    'sensor.example_14': '25.2', 'sensor.example_15': '19.8', 'sensor.example_16': '23.9', 'sensor.example_33': '20.1', 'sensor.example_34': '29.4', 'sensor.example_35': '17.2',
    'input_text.example_20': 'open|100|2026-10-20', 'input_datetime.example_21': '15:00:00', 'input_datetime.example_22': '17:00:00',
    'input_number.example_24': '30', 'input_boolean.example_25': 'on', 'sensor.example_31': '7', 'sensor.example_32': 'ok',
}
ATTRS = {
    'weather.example_37': {'temperature': 24.5, 'temperature_unit': '°C', 'humidity': 52, 'wind_speed': 14, 'wind_speed_unit': 'km/h', 'wind_bearing': 120, 'cloud_coverage': 40},
    'climate.example_17': {'hvac_action': 'off', 'temperature': 22, 'current_temperature': 23.1, 'fan_mode': 'auto'},
    'sensor.example_31': {'days': [
        {'date': '2026-10-17', 'house': 10.1, 'solar': 21.0, 'export': 9.8, 'paid': 0.62, 'free': 2.9},
        {'date': '2026-10-18', 'house': 11.4, 'solar': 15.2, 'export': 4.1, 'paid': 1.05, 'free': 3.4},
        {'date': '2026-10-19', 'house': 9.7, 'solar': 22.3, 'export': 11.0, 'paid': 0.38, 'free': 2.6},
        {'date': '2026-10-20', 'house': 10.6, 'solar': 19.9, 'export': 8.7, 'paid': 0.55, 'free': 3.0}]},
    'sensor.example_32': {'month': '2026-10', 'nights': [
        {'date': '2026-10-18', 'result': 'met'}, {'date': '2026-10-19', 'result': 'met'}, {'date': '2026-10-20', 'result': 'missed'},
        {'date': '2026-10-21', 'result': 'no data'}]},
}


class _St:
    def __init__(self, eid, state, attrs, last_updated):
        self.entity_id, self.state, self.attributes, self.last_updated = eid, state, attrs, last_updated


def render(house, now: datetime | None = None) -> str:
    """The rendered go-live prompt (the agent's own prompt) for this fake house at `now` (default: the house clock, Sydney time)."""
    from atlas_household.fake import SYDNEY
    now = (now or house.clock).astimezone(SYDNEY)
    singles = {h: t for h, t in sorted(house.coord.handles.items(), key=lambda x: not x[0].endswith('_lights'))      # a light's own label wins
               if t['kind'] == 'light' and len(t['entity_ids']) == 1 and t.get('area')}
    area = {t['entity_ids'][0]: t['area'] for t in singles.values()}
    names = {t['entity_ids'][0]: t['label'] for t in singles.values()}
    lights = sorted(area)
    covers = [e for h in ('sunroom_blind', 'family_room_window_blind', 'family_room_door_blind') for e in house.coord.handles[h]['entity_ids']]
    cover_names = {e: house.coord.handles[h]['label'] for h in ('sunroom_blind', 'family_room_window_blind', 'family_room_door_blind') for e in house.coord.handles[h]['entity_ids']}

    def live(eid):
        st = house.backend.states.get(eid)
        if eid.startswith('light.') and st:
            a = {'friendly_name': names.get(eid, eid), 'brightness': st['attributes'].get('brightness')}
            return st['state'], a
        if eid.startswith('cover.') and st:
            return st['state'], {'friendly_name': cover_names.get(eid, eid), 'current_position': st['attributes'].get('current_position')}
        if eid in READINGS:
            return READINGS[eid], ATTRS.get(eid, {})
        return 'unknown', {}

    def states(eid):
        return live(eid)[0]

    class States:
        def __call__(self, eid):
            return states(eid)

        def __getitem__(self, eid):
            s, a = live(eid)
            return _St(eid, s, a, now - timedelta(minutes=10))

        def __iter__(self):
            return iter([self[e] for e in list(READINGS) + lights + covers])

    def state_attr(eid, a):
        return live(eid)[1].get(a)

    def is_number(v):
        try:
            float(v)
            return not isinstance(v, bool)
        except (TypeError, ValueError):
            return False

    def flt(v, default=0.0):
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    def itg(v, default=0):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return default

    env = jinja2.Environment(extensions=['jinja2.ext.loopcontrols'], undefined=jinja2.ChainableUndefined)
    env.tests['match'] = lambda v, rx: bool(re.match(rx, str(v)))
    env.tests['is_number'] = is_number
    env.tests['list'] = lambda v: isinstance(v, list)
    env.tests['number'] = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    env.filters['float'] = flt
    env.filters['int'] = itg
    env.filters['is_number'] = is_number
    env.globals.update(now=lambda: now, states=States(), state_attr=state_attr, is_state=lambda e, s: states(e) == s, area_name=lambda e: area.get(e),
                       as_datetime=lambda v: datetime.fromisoformat(str(v)), timedelta=timedelta, is_number=is_number, dict=dict)
    src = adapt(TEMPLATE.read_text(encoding='utf-8'), lights, covers)
    return env.from_string(src).render()


def system_prompt(house, now: datetime | None = None) -> str:
    """What HA sends as the system message: the agent's rendered prompt, then the coordinator's API prompt (tools.system_prompt)."""
    return house.system_prompt(render(house, now))


if __name__ == '__main__':
    from fixture import house as mk
    print(system_prompt(mk()))
