"""Render the real go-live prompt (prompt-build/prompt-template.golive.jinja, byte for byte) with a small HA-like Jinja stub fed by a case's
synthetic readings, and build the candidate prompt from the same template. Test harness only: nothing here talks to HA or a house.

Arms:
  current  - the go-live template exactly as exported (its energy rules, the "Good advice" and "at night the cheapest choice is usually to
             wait" lines, "Never invent or estimate a figure"), with the coordinator's tools.
  candidate - the same template with three edits (the integration patch, PATCH below): line 41 replaced by guidance.txt; the two rejected
             fixed-advice lines removed from the energy rules; the energy cards inserted after the rules. Plus the atlas_calc tool.
Codex 49's text fact snapshots go to BOTH arms in the same place (identical evidence; only the guidance differs), as EVALUATION.md asks.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import jinja2
from jinja2.sandbox import ImmutableSandboxedEnvironment

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'custom_components'))
from atlas_household import tools as T  # noqa: E402

TEMPLATE = (HERE.parent / 'prompt-build' / 'prompt-template.golive.jinja').read_text(encoding='utf-8')
GUIDANCE = (HERE / 'guidance.txt').read_text(encoding='utf-8').rstrip('\n')
HANDLES = json.loads((ROOT / 'custom_components' / 'atlas_household' / 'targets.json').read_text())['handles']
SYDNEY = __import__('zoneinfo').ZoneInfo('Australia/Sydney')

OLD_Q = ("Questions: answer only from the readings. Never invent or estimate a figure. You don't have the energy forecast, so never promise the "
         "battery will last; say what the readings show.")
OLD_ADVICE = ["- Good advice: run big loads (washing, dishwasher, heating or cooling boosts) in 11:00–14:00 when you can. Avoid big loads 6–8 pm.\n",
              "- Outside 11:00–14:00 grid power is paid; the credit hours matter only from 6 pm to 8 pm. So at night the cheapest choice is usually to "
              "wait for tomorrow's free window, and there's no credit risk.\n"]
OLD_AC = "A question about them (what mode it is in, whether a TV is on) is answered from the readings, like any other question."
NEW_AC = ("A question about them (what mode it is in, whether a TV is on, whether or when to use the aircon) is answered from the readings and "
          "the energy cards, like any other question: give the advice, and don't answer it with \"I can't control that\".")
CARDS_ANCHOR = '\nEnergy history (kWh.'
CARDS_SLOT = '{{ atlas_energy_cards }}'


def candidate_template() -> str:
    t = TEMPLATE
    assert t.count(OLD_Q) == 1 and all(t.count(x) == 1 for x in OLD_ADVICE) and t.count(CARDS_ANCHOR) == 1
    assert t.count(OLD_AC) == 1
    t = t.replace(OLD_Q, GUIDANCE).replace(OLD_AC, NEW_AC)          # round 2: an aircon question is advice, not a refused command
    for x in OLD_ADVICE:
        t = t.replace(x, '')
    return t.replace(CARDS_ANCHOR, '\n' + CARDS_SLOT + '\n' + CARDS_ANCHOR, 1)


def current_template() -> str:
    assert TEMPLATE.count(CARDS_ANCHOR) == 1
    return TEMPLATE.replace(CARDS_ANCHOR, '\n' + CARDS_SLOT + '\n' + CARDS_ANCHOR, 1)   # empty for own cases; Codex snapshots only


class St:
    def __init__(self, entity_id, state, attributes=None, at=None):
        self.entity_id, self.state, self.attributes = entity_id, str(state), dict(attributes or {})
        self.last_reported = self.last_updated = self.last_changed = at


class States:
    def __init__(self, d):
        self.d = d

    def __call__(self, eid):
        s = self.d.get(eid)
        return 'unknown' if s is None else s.state

    def __getitem__(self, eid):
        return self.d.get(eid)

    def __iter__(self):
        return iter(self.d.values())


ROOMS = ['Living Room', 'Kitchen', 'Dining Room', 'Hallway', 'Atrium', 'Master Bedroom', 'Laundry', 'Garage', 'Loft', 'Study', 'Guest Bedroom',
         'Patio', 'Porch']
LIGHT_IDS = re.findall(r'"(light\.example_\d+)"', TEMPLATE)


def house_states(now: datetime, h: dict) -> dict:
    """h: the case's readings (synthetic). Unknown keys -> 'unavailable'. Values may be {'value', 'at'} for a stale reading."""
    S = {}

    def put(eid, key, attrs=None):
        v = h.get(key)
        at = now
        if isinstance(v, dict):
            v, at = v.get('value'), datetime.fromisoformat(v['at']) if isinstance(v.get('at'), str) else v.get('at', now)
        S[eid] = St(eid, 'unavailable' if v is None else v, attrs, at)
    for eid, key in [('sensor.example_01', 'soc'), ('sensor.example_04', 'solar_w'), ('sensor.example_05', 'house_w'), ('sensor.example_27', 'import_w'),
                     ('sensor.example_28', 'export_w'), ('sensor.example_36', 'solar_today'), ('sensor.example_06', 'house_today'),
                     ('sensor.example_07', 'solar_today'), ('sensor.example_09', 'paid_today'), ('sensor.example_10', 'free_today'),
                     ('sensor.example_08', 'export_today'), ('sensor.example_11', 'loft'), ('sensor.example_13', 'humidor'),
                     ('sensor.example_12', 'bedroom'), ('sensor.example_26', 'garage'), ('sensor.example_14', 'loft_high'), ('sensor.example_15', 'loft_low'),
                     ('sensor.example_16', 'bedroom_high'), ('sensor.example_33', 'bedroom_low'), ('sensor.example_34', 'garage_high'),
                     ('sensor.example_35', 'garage_low'), ('input_text.example_03', 'forecast_days'), ('input_text.example_30', 'forecast_24h')]:
        put(eid, key)
    S['weather.example_37'] = St('weather.example_37', h.get('weather', 'unavailable'),
                                 {'temperature': h.get('outside_c'), 'temperature_unit': '°C', 'humidity': h.get('humidity'), 'wind_speed': h.get('wind'),
                                  'wind_speed_unit': 'km/h'} if h.get('weather') else {}, now)
    S['climate.example_17'] = St('climate.example_17', h.get('ac_mode', 'off'), {'hvac_action': h.get('ac_action', 'off'), 'temperature': 24,
                                                                                'current_temperature': h.get('loft'), 'fan_mode': 'auto'}, now)
    S['todo.household_reminders'] = St('todo.household_reminders', 1, {}, now)
    S['binary_sensor.example_18'] = St('binary_sensor.example_18', 'off', {}, now)
    S['binary_sensor.example_19'] = St('binary_sensor.example_19', 'off', {}, now)
    S['input_datetime.example_38'] = St('input_datetime.example_38', (now.date() - timedelta(days=5)).isoformat(), {}, now)
    S['input_datetime.example_39'] = St('input_datetime.example_39', (now.date() - timedelta(days=2)).isoformat(), {}, now)
    on = set(h.get('lights_on', []))
    for i, eid in enumerate(LIGHT_IDS):
        area = ROOMS[i % len(ROOMS)]
        S[eid] = St(eid, 'on' if i in on else 'off', {'friendly_name': f'{area} Light {i // len(ROOMS) + 1}', 'brightness': 200 if i in on else None,
                                                     '_area': area}, now)
    for eid, name, pos in [('cover.example_23', 'Atrium Blind', 100), ('cover.example_106', 'Living Room Window Blind', 0),
                           ('cover.example_107', 'Living Room Door Blind', 0)]:
        S[eid] = St(eid, 'open' if pos else 'closed', {'friendly_name': name, 'current_position': pos}, now)
    S['input_text.example_20'] = St('input_text.example_20', '', {}, now)
    S['input_datetime.example_21'] = St('input_datetime.example_21', '07:30:00', {}, now)
    S['input_datetime.example_22'] = St('input_datetime.example_22', '15:00:00', {}, now)
    S['input_number.example_24'] = St('input_number.example_24', '40.0', {}, now)
    S['input_boolean.example_25'] = St('input_boolean.example_25', 'off', {}, now)
    S['sensor.example_31'] = St('sensor.example_31', len(h.get('days', [])), {'days': h.get('days', [])}, now)
    S['sensor.example_32'] = St('sensor.example_32', 'ok', {'nights': h.get('nights', []), 'month': now.strftime('%Y-%m')}, now)
    return S


def _is_number(v) -> bool:
    if isinstance(v, bool):
        return False
    try:
        x = float(v)
    except (TypeError, ValueError):
        return False
    return x == x and x not in (float('inf'), float('-inf'))


def _float(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        if default is None:
            raise
        return default


def _int(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def env(now: datetime, S: dict) -> ImmutableSandboxedEnvironment:
    e = ImmutableSandboxedEnvironment(undefined=jinja2.Undefined)
    st = States(S)
    e.globals.update(now=lambda: now, states=st, timedelta=timedelta, is_number=_is_number,
                     state_attr=lambda i, a: (S[i].attributes.get(a) if i in S else None),
                     is_state=lambda i, v: i in S and S[i].state == v,
                     area_name=lambda i: S[i].attributes.get('_area') if i in S else None,
                     as_datetime=lambda v: datetime.fromisoformat(v) if isinstance(v, str) else v)
    e.filters.update(float=_float, int=_int, is_number=_is_number, as_local=lambda t: t.astimezone(SYDNEY),
                     as_timestamp=lambda t: t.timestamp(), timestamp_custom=lambda ts, f: datetime.fromtimestamp(ts, SYDNEY).strftime(f))
    e.tests.update(match=lambda v, p: re.match(p, str(v)) is not None, is_number=_is_number, list=lambda v: isinstance(v, list))
    return e


def render(arm: str, now: datetime, house: dict, cards_text: str = '') -> str:
    tpl = candidate_template() if arm.startswith('candidate') else current_template()
    out = env(now, house_states(now, house)).from_string(tpl).render(atlas_energy_cards=cards_text)
    return out.rstrip('\n')


def system_prompt(arm: str, now: datetime, house: dict, cards_text: str = '') -> str:
    """As HA joins them: the agent's rendered prompt, then the coordinator's API prompt (tools.system_prompt)."""
    return T.system_prompt(render(arm, now, house, cards_text), HANDLES)


def tool_specs(arm: str) -> list[dict]:
    import calc  # noqa: PLC0415
    specs = T.tool_specs(HANDLES, timer_blinds=False)
    if arm.startswith('candidate'):
        n, d, p, r = calc.TOOL_SPEC
        specs.append({'type': 'function', 'function': {'name': n, 'description': d, 'parameters': {'type': 'object', 'properties': p, 'required': r}}})
    return specs


if __name__ == '__main__':
    now = datetime(2026, 10, 20, 20, 47, tzinfo=SYDNEY)
    print(system_prompt(sys.argv[1] if len(sys.argv) > 1 else 'candidate', now, {'soc': 61, 'solar_w': 0, 'house_w': 620}, '- (cards here)'))
