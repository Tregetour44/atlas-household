"""Atlas coordinator: the recording fake. It sends NOTHING to the house: every service call is recorded and applied to an in-memory state dict,
and the real coordinator core runs on top, so results have exactly the real shapes.

Typical use (the Atlas-side project's runner). The clock is UTC-aware like HA's; the Sydney zone is used for labels and "at HH:MM".
    import sys; sys.path.insert(0, r'custom_components')
    from atlas_household.fake import FakeHouse
    house = FakeHouse()                       # loads targets.json; every light off, blinds closed, at a fixed Sydney time
    house.set('light.office_ceiling', 'on', brightness_percent=60)
    res = house.call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'off'}, user_text='turn the office light off')
    house.calls                               # [{'domain': 'light', 'service': 'turn_off', 'entity_ids': [...], 'data': {}}]
    q = house.call('atlas_blind', {...}); house.call('atlas_confirm', {'confirmation': q['confirmation']}, user_text='yes', last_reply=what_atlas_said)
    house.advance(minutes=15); house.tick()   # run due timers
    house.tools                               # tool specs in HA's real Ollama format; house.system_prompt(atlas_prompt) for the slot
Faults for tests: house.no_readback.add(entity_id) (the device ignores the call), house.raise_on_call = True (transport error).
"""
from __future__ import annotations

import asyncio
import copy
import json
import pathlib
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .core import Coordinator
from .tools import system_prompt, tool_specs

try:
    SYDNEY = ZoneInfo('Australia/Sydney')
except ZoneInfoNotFoundError:      # Windows Python without tzdata: daylight time (AEDT) runs 4 Oct 2026 to 5 Apr 2027, so fixed +11:00 is right here
    SYDNEY = timezone(timedelta(hours=11), 'AEDT')
TARGETS = pathlib.Path(__file__).with_name('targets.json')


class FakeBackend:
    def __init__(self, states: dict) -> None:
        self.states = states
        self.calls: list[dict] = []
        self.no_readback: set[str] = set()
        self.raise_on_call = False
        self.scene_expect: dict = {}
        self.revs = 0

    def touch(self, entity_id: str) -> None:
        """A state change: HA moves last_changed (the coordinator's change revision)."""
        self.revs += 1
        self.states[entity_id]['last_changed'] = f'rev-{self.revs}'

    async def get_state(self, entity_id):
        st = self.states.get(entity_id)
        return {'entity_id': entity_id, **copy.deepcopy(st)} if st else None

    async def call(self, domain, service, entity_ids, data):
        await asyncio.sleep(0)       # yield, as HA's service call does, so a racing cancel really interleaves
        self.calls.append({'domain': domain, 'service': service, 'entity_ids': list(entity_ids), 'data': dict(data)})
        if self.raise_on_call:
            raise ConnectionError('fake transport failure')
        for e in entity_ids:
            if e in self.no_readback or e not in self.states:
                continue
            st, a = self.states[e], self.states[e]['attributes']
            old = st['state']
            if domain == 'light':
                if service == 'turn_off':
                    st['state'] = 'off'
                    a['brightness'] = None
                else:
                    st['state'] = 'on'
                    a['brightness'] = round(data['brightness_pct'] * 2.55) if 'brightness_pct' in data else (a.get('brightness') or 255)
                    if 'color_temp_kelvin' in data:
                        a['color_temp_kelvin'], a['color_mode'] = data['color_temp_kelvin'], 'color_temp'
                    if 'hs_color' in data:
                        a['hs_color'], a['color_mode'] = list(data['hs_color']), 'hs'
                    if 'effect' in data:
                        a['effect'] = data['effect']
            elif domain == 'cover':
                pos = 100 if service == 'open_cover' else 0 if service == 'close_cover' else data['position']
                a['current_position'] = pos
                st['state'] = 'closed' if pos == 0 else 'open'
            elif domain == 'scene':
                for m, w in (self.scene_expect.get(e) or {}).items():
                    if m in self.states and m not in self.no_readback:
                        was = self.states[m]['state']
                        ma = self.states[m]['attributes']
                        self.states[m]['state'] = w['state']
                        ma['brightness'] = round(w['brightness_percent'] * 2.55) if w.get('brightness_percent') else (255 if w['state'] == 'on' else None)
                        for k in ('color_temp_kelvin', 'hs_color', 'effect'):
                            if k in w:
                                ma[k] = w[k]
                        if 'color_temp_kelvin' in w:
                            ma['color_mode'] = 'color_temp'
                        elif 'hs_color' in w:
                            ma['color_mode'] = 'hs'
                        if w['state'] != was:
                            self.touch(m)
                st['state'] = datetime.now(SYDNEY).isoformat()
            if st['state'] != old:
                self.touch(e)

    async def wait_for(self, entity_id, predicate, timeout):
        return await self.get_state(entity_id)


class MemoryStore:
    def __init__(self) -> None:
        self.data = None
        self.saves = 0

    async def load(self):
        return copy.deepcopy(self.data)

    async def save(self, data):
        self.data = json.loads(json.dumps(data))      # must be JSON-clean, as HA's Store is
        self.saves += 1


class FakeHouse:
    def __init__(self, targets: dict | None = None, start: datetime | None = None, store: MemoryStore | None = None, states: dict | None = None) -> None:
        self.targets = targets or json.loads(TARGETS.read_text(encoding='utf-8'))
        self.clock = (start or datetime(2026, 10, 18, 19, 30, tzinfo=SYDNEY)).astimezone(timezone.utc)   # UTC, as HA's dt_util.utcnow()
        self.mono = 1000.0                                                                                   # the monotonic clock
        if states is None:
            states = {}
            for t in self.targets['handles'].values():
                for e in t['entity_ids'] + t.get('members', []):
                    dom = e.split('.')[0]
                    states[e] = {'light': {'state': 'off', 'attributes': {'friendly_name': e}},
                                 'cover': {'state': 'closed', 'attributes': {'current_position': 0, 'supported_features': 15}},
                                 'scene': {'state': 'unknown', 'attributes': {}},
                                 'media_player': {'state': 'off', 'attributes': {}}}[dom]
        for e, cls in (self.targets.get('reviewed_covers') or {}).items():
            if e in states and cls is not None:
                states[e]['attributes'].setdefault('device_class', cls)
        for t in self.targets['handles'].values():
            if t['kind'] == 'scene' and t.get('members') and t['entity_ids'][0] in states:
                states[t['entity_ids'][0]]['attributes'].setdefault('entity_id', list(t['members']))
        self.backend = FakeBackend(states)
        self.backend.scene_expect = {t['entity_ids'][0]: t['expect'] for t in self.targets['handles'].values() if t['kind'] == 'scene' and t.get('expect')}
        self.store = store or MemoryStore()
        self.loop = asyncio.new_event_loop()
        self._turns = 0
        self._make()

    def _make(self) -> None:
        self.coord = Coordinator(self.targets, self.backend, self.store, lambda: self.clock, SYDNEY, mono=lambda: self.mono)
        self.started = self.loop.run_until_complete(self.coord.start())
        self.rebased = self.loop.run_until_complete(self.coord.rebaseline())   # in HA: once Home Assistant has started

    # --- driving ---
    def call(self, tool: str, args: dict, *, user_text: str = '', conversation_id: str = 'conv-1', turn: str | None = None,
             last_reply: str | None = None, request_id: str | None = None) -> dict:
        """Each call is a new user turn unless turn= names the same one (several tool calls answering one utterance share a turn).
        last_reply = Atlas's previous reply in this conversation (HA reads it from the chat log): atlas_confirm needs it to contain the question."""
        if turn is None:
            self._turns += 1
            turn = f't{self._turns}'
        return self.loop.run_until_complete(self.coord.call_tool(tool, args, conversation_id=conversation_id, user_text=user_text, turn=turn,
                                                                 last_reply=last_reply, request_id=request_id))

    def tick(self) -> list[dict]:
        return self.loop.run_until_complete(self.coord.tick())

    def advance(self, **kw) -> None:
        """Real time passes: the wall clock and the monotonic clock move together."""
        d = timedelta(**kw)
        self.clock += d
        self.mono += d.total_seconds()

    def jump_clock(self, **kw) -> None:
        """The wall clock alone is changed (NTP step, manual change); the monotonic clock doesn't move."""
        self.clock += timedelta(**kw)

    def restart(self, down_for: timedelta = timedelta(minutes=2)) -> list[dict]:
        """Simulate an HA restart: memory is lost (pending yes-questions too), the durable store survives."""
        self.clock += down_for
        self.mono += down_for.total_seconds()
        for e in self.backend.states:      # HA resets every entity's last_changed when it starts
            self.backend.touch(e)
        self._make()
        return self.started

    def set(self, entity_id: str, state: str, *, brightness_percent: int | None = None, position_percent: int | None = None) -> None:
        """A change made by hand (or by anything other than Atlas): moves the change revision."""
        st = self.backend.states.setdefault(entity_id, {'state': state, 'attributes': {}})
        st['state'] = state
        self.backend.touch(entity_id)
        if brightness_percent is not None:
            st['attributes']['brightness'] = round(brightness_percent * 2.55)
        elif entity_id.startswith('light.'):
            st['attributes']['brightness'] = 255 if state == 'on' else None
        if position_percent is not None:
            st['attributes']['current_position'] = position_percent

    # --- reading ---
    @property
    def calls(self) -> list[dict]:
        return self.backend.calls

    @property
    def no_readback(self) -> set:
        return self.backend.no_readback

    @property
    def raise_on_call(self) -> bool:
        return self.backend.raise_on_call

    @raise_on_call.setter
    def raise_on_call(self, v: bool) -> None:
        self.backend.raise_on_call = v

    @property
    def tools(self) -> list[dict]:
        return tool_specs(self.coord.handles, self.coord.timer_blinds)

    def system_prompt(self, atlas_prompt: str) -> str:
        return system_prompt(atlas_prompt, self.coord.handles)

    def state(self, entity_id: str) -> dict | None:
        return copy.deepcopy(self.backend.states.get(entity_id))
