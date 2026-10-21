"""The rehearsal fixture: the synthetic phase-2 map (atlas-current/targets.synthetic-phase2.json) as the live phase-2 shape needs it, plus a
FakeHouse factory with the canonical evening state. Synthetic only: no household names, ids or addresses.

Two documented changes to the phase-2 map, both to mirror the live phase-2 shape (bc08ea4):
  - the two enabled scenes carry the live handles and labels (lights_out -> good_night "Good Night", unwind -> wind_down "Wind Down"; the
    map's own note says lights_out ~ Good Night and unwind ~ Wind Down), so the go-live prompt's "atlas_scene (good_night or wind_down)" holds;
  - they get synthetic reviewed members and expected states (the phase-2 export has none, so atlas_scene would not even be offered).
Room names stay synthetic (Sunroom ~ the live Atrium, Family Room ~ the live Living Room, Office ~ the live Study); prompt.py adapts the
go-live prompt's place lines with the same table, and generate.py translates the owner's phrasings with it.
"""
from __future__ import annotations

import copy
import json
import os
import pathlib
import sys
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = os.environ.get('ATLAS_PKG') or str(ROOT / 'custom_components')     # ATLAS_PKG: another copy of custom_components (e.g. the input branch)
sys.path.insert(0, PKG)
from atlas_household.fake import SYDNEY, FakeHouse  # noqa: E402

PHASE2 = ROOT / 'atlas-current' / 'targets.synthetic-phase2.json'
FIXTURE = ROOT / 'rehearsal-set' / 'targets.rehearsal.json'
EVENING = datetime(2026, 10, 21, 19, 30, tzinfo=SYDNEY)      # 7:30 pm: inside the 6-8 pm credit window, lights on, blinds open

LIVE_TO_SYNTHETIC = [            # the owner's real place words -> the synthetic map's (used for the prompt and the owner phrasings)
    ('living room', 'family room'), ('Living Room', 'Family Room'), ('lounge room', 'family room'), ('atrium', 'sunroom'), ('Atrium', 'Sunroom'),
    ('study', 'office'), ('Study', 'Office'), ('porch', 'entry'), ('Porch', 'Entry'), ('patio', 'deck'), ('Patio', 'Deck'),
    ('loft', 'attic'), ('Loft', 'Attic'), ('kitchen', 'galley'), ('Kitchen', 'Galley'), ('hallway', 'corridor'), ('Hallway', 'Corridor'),
    ('laundry', 'utility'), ('Laundry', 'Utility'), ('master bedroom', 'bedroom south'), ('Master Bedroom', 'Bedroom South'),
]

GOOD_NIGHT = {e: {'state': 'off'} for e in [
    'light.attic_downlight_left', 'light.attic_downlight_middle', 'light.attic_downlight_right', 'light.office_ceiling',
    'light.family_room_lamp', 'light.family_room_downlight_front', 'light.family_room_downlight_back', 'light.mirror_glow',
    'light.galley_ceiling', 'light.galley_pendant', 'light.sunroom_spotlight_left', 'light.sunroom_spotlight_right', 'light.sunroom_floor_lamp',
    'light.utility_downlight', 'light.carport_ceiling_left', 'light.carport_ceiling_right', 'light.workshop_bench_light',
    'light.yard_spot', 'light.wall_lamp', 'light.flood_lamp', 'light.entry_downlight_1', 'light.entry_downlight_2']}
GOOD_NIGHT.update({'light.corridor_downlight': {'state': 'on', 'brightness_percent': 10}, 'light.bedroom_south_lamp': {'state': 'on', 'brightness_percent': 20},
                   'light.attic_lamp': {'state': 'off'}})
WIND_DOWN = {'light.family_room_lamp': {'state': 'on', 'brightness_percent': 35}, 'light.family_room_downlight_front': {'state': 'off'},
             'light.family_room_downlight_back': {'state': 'off'}, 'light.mirror_glow': {'state': 'on', 'brightness_percent': 25},
             'light.galley_ceiling': {'state': 'off'}, 'light.galley_pendant': {'state': 'on', 'brightness_percent': 30},
             'light.sunroom_floor_lamp': {'state': 'on', 'brightness_percent': 30}, 'light.sunroom_spotlight_left': {'state': 'off'},
             'light.sunroom_spotlight_right': {'state': 'off'}}


def build_targets() -> dict:
    d = json.loads(PHASE2.read_text(encoding='utf-8'))
    hs = d['handles']
    out = {}
    for h, t in hs.items():
        if h == 'lights_out':
            out['good_night'] = {**t, 'entity_ids': ['scene.good_night'], 'label': 'Good Night', 'members': sorted(GOOD_NIGHT), 'expect': GOOD_NIGHT,
                                 'contents_frozen_offline': True}
        elif h == 'unwind':
            out['wind_down'] = {**t, 'entity_ids': ['scene.wind_down'], 'label': 'Wind Down', 'members': sorted(WIND_DOWN), 'expect': WIND_DOWN,
                                'contents_frozen_offline': True}
        else:
            out[h] = t
    d['handles'] = out
    d['version'] = 'synthetic-rehearsal-1'
    d['note'] = ('Rehearsal fixture (synthetic; never installable): atlas-current/targets.synthetic-phase2.json with the two enabled scenes under '
                 'their live handles (good_night, wind_down) and synthetic reviewed members. Built by rehearsal/fixture.py.')
    return d


def write_fixture() -> pathlib.Path:
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(build_targets(), indent=1) + '\n', encoding='utf-8')
    return FIXTURE


CANONICAL_ON = {'light.family_room_lamp': 60, 'light.family_room_downlight_front': 100, 'light.family_room_downlight_back': 100,
                'light.galley_ceiling': 100, 'light.office_ceiling': 80, 'light.yard_spot': 100, 'light.flood_lamp': 100, 'light.corridor_downlight': 40}
CANONICAL_BLINDS = {'cover.blind_motor': 100, 'cover.blind_motor_2': 100, 'cover.blind_motor_3': 50}


def house(start: datetime = EVENING, preset: str = 'canonical') -> FakeHouse:
    """A FakeHouse on the fixture. 'canonical': the evening state every model case starts from (so the rendered prompt is identical and the
    model's prompt cache holds); 'dark': every light off, blinds closed (the FakeHouse default); 'bright': every light on 100%, blinds open."""
    h = FakeHouse(targets=build_targets(), start=start)
    if preset == 'canonical':
        for e, pct in CANONICAL_ON.items():
            h.set(e, 'on', brightness_percent=pct)
        for e, pos in CANONICAL_BLINDS.items():
            h.set(e, 'open', position_percent=pos)
    elif preset == 'bright':
        for e, st in h.backend.states.items():
            if e.startswith('light.'):
                h.set(e, 'on', brightness_percent=100)
            elif e.startswith('cover.'):
                h.set(e, 'open', position_percent=100)
    h.calls.clear()
    return h


def snapshot(h: FakeHouse) -> dict:
    return copy.deepcopy({e: {'state': s['state'], 'brightness': s['attributes'].get('brightness'), 'position': s['attributes'].get('current_position')}
                          for e, s in h.backend.states.items() if not e.startswith('scene.')})


if __name__ == '__main__':
    print(write_fixture())
