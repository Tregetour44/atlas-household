"""Atlas household coordinator (custom integration; directive Lead 20261018-0142). Built and tested on the Docker test copy only.

core.py, tools.py and fake.py are pure Python (no Home Assistant import), so this file must not import Home Assistant at module level:
the Atlas-side project's runner imports atlas_household.fake outside HA. All HA imports are inside the functions below.

Setup: load the chosen target map (only a FROZEN household map, or the demo map on the test copy), open the durable store, start the
coordinator (missed timers are cancelled and shown as a notification), register the "Atlas household" LLM API, and once Home Assistant has
started, re-check timers still to come and arm a callback for the next one. Unload: cancel pending timers, unregister the API, disarm.
"""
from __future__ import annotations

import asyncio

import json
import pathlib

DOMAIN = 'atlas_household'
HERE = pathlib.Path(__file__).parent
TEST_COPY_NAME = 'Atlas test copy'     # homeassistant: name: in the test copy's configuration.yaml; the household HA is not called this


class Runtime:
    def __init__(self, hass, coord, backend) -> None:
        self.hass, self.coord, self.backend = hass, coord, backend
        self.unsub_timer = None

    async def call(self, tool, args, conversation_id, user_text, turn, last_reply, llm_context, request_id=None):
        from homeassistant.core import Context  # noqa: PLC0415
        parent = getattr(llm_context, 'context', None)
        self.backend.context = Context(user_id=getattr(parent, 'user_id', None), parent_id=getattr(parent, 'id', None))
        try:
            return await self.coord.call_tool(tool, args, conversation_id=conversation_id, user_text=user_text, turn=turn,
                                              last_reply=last_reply, request_id=request_id)
        finally:
            self.backend.context = None
            self.arm()

    def arm(self) -> None:
        from homeassistant.helpers.event import async_track_point_in_utc_time  # noqa: PLC0415
        if self.unsub_timer:
            self.unsub_timer()
            self.unsub_timer = None
        due = self.coord.next_due()
        if due is not None and self.coord.ready:
            self.unsub_timer = async_track_point_in_utc_time(self.hass, self._fire, due)

    async def _fire(self, _now) -> None:
        self.unsub_timer = None
        from homeassistant.core import Context  # noqa: PLC0415
        self.backend.context = Context()
        try:
            await self.coord.tick()
        finally:
            self.backend.context = None
            self.notify()
            self.arm()

    async def ready(self, _event=None) -> None:
        await self.coord.rebaseline()
        self.notify()
        self.arm()

    def notify(self) -> None:
        from homeassistant.components import persistent_notification  # noqa: PLC0415
        words = {'cancelled_missed': 'cancelled, not run late', 'cancelled_changed': 'cancelled', 'cancelled': 'cancelled', 'needs_review': 'stopped for a check', 'ran_not_confirmed': "ran, but it couldn't be confirmed", 'did_not_run': "didn't run",
                 'could_not_reach': "couldn't reach the device",
                 'outcome_unknown': "may or may not have happened; it wasn't repeated"}
        while self.coord.notices:
            n = self.coord.notices.pop(0)
            persistent_notification.async_create(self.hass, f"Atlas timer {n['label']}: {words.get(n['kind'], n['kind'])}, because {n['reason']}.",
                                                 title='Atlas timer', notification_id=f"atlas_{n['task']}")


async def async_setup_entry(hass, entry) -> bool:
    from homeassistant.helpers.start import async_at_started  # noqa: PLC0415
    from homeassistant.exceptions import ConfigEntryError  # noqa: PLC0415
    from homeassistant.helpers import llm  # noqa: PLC0415
    from homeassistant.helpers.storage import Store  # noqa: PLC0415
    from homeassistant.util import dt as dt_util  # noqa: PLC0415
    from .api import AtlasAPI, HABackend  # noqa: PLC0415
    from .core import Coordinator, installable  # noqa: PLC0415

    name = entry.data['targets']
    if '/' in name or '\\' in name or not name.startswith('targets') or not name.endswith('.json'):
        raise ConfigEntryError('bad target map name')
    targets = json.loads(await hass.async_add_executor_job((HERE / name).read_text, 'utf-8'))
    if err := installable(targets):
        raise ConfigEntryError(f'Atlas coordinator not started: {err}')
    test_copy = targets.get('test_only') is True
    if test_copy and hass.config.location_name != TEST_COPY_NAME:
        raise ConfigEntryError('the demo map runs only on the Atlas test copy')
    store = Store(hass, 1, f'{DOMAIN}.data')

    class _Store:
        async def load(self):
            return await store.async_load()

        async def save(self, data):
            await store.async_save(data)

    backend = HABackend(hass)
    coord = Coordinator(targets, backend, _Store(), dt_util.utcnow, dt_util.get_default_time_zone())
    rt = Runtime(hass, coord, backend)
    await coord.start()
    rt.notify()
    unreg = llm.async_register_api(hass, AtlasAPI(hass, rt))
    entry.runtime_data = rt
    entry.async_on_unload(async_at_started(hass, rt.ready))   # now if HA has fully started, else once it has (states loaded)
    if test_copy:
        _register_test_services(hass, rt)
    rt.guarded_loaded = False
    rt.options_lock = asyncio.Lock()
    if (entry.options or {}).get('guarded_agent'):          # the claim-guarded agent, only when an underlying agent is configured
        await hass.config_entries.async_forward_entry_setups(entry, ['conversation'])
        rt.guarded_loaded = True
    entry.async_on_unload(entry.add_update_listener(_options_changed))

    def _unload():
        unreg()
        if rt.unsub_timer:
            rt.unsub_timer()
        if test_copy:
            for svc in ('test_call', 'test_state'):
                hass.services.async_remove(DOMAIN, svc)

    entry.async_on_unload(_unload)
    return True


def _register_test_services(hass, rt) -> None:
    """TEST COPY ONLY (demo map + the test copy's name). atlas_household.test_call drives a tool through HA's real LLM API path (the registered
    API, its tools and the current chat log, as a conversation agent would), with a given user utterance and the previous assistant reply;
    test_state returns the coordinator's store, its tool specs (HA's conversion) and its API prompt. Removed on unload."""
    import voluptuous as vol  # noqa: PLC0415
    from homeassistant.components.conversation.chat_log import AssistantContent, UserContent, async_get_chat_log  # noqa: PLC0415
    from homeassistant.core import SupportsResponse  # noqa: PLC0415
    from homeassistant.helpers import chat_session, llm  # noqa: PLC0415

    def ctx(call):
        return llm.LLMContext(platform='atlas_test', context=call.context, language='en', assistant='conversation', device_id=None)

    async def test_call(call):
        with chat_session.async_get_chat_session(hass, call.data['conversation_id']) as session, async_get_chat_log(hass, session) as chat_log:
            if call.data.get('last_reply'):
                chat_log.content.append(AssistantContent(agent_id='atlas_test', content=call.data['last_reply']))
            if call.data.get('new_turn', True):
                chat_log.async_add_user_content(UserContent(content=call.data.get('user_text', '')))
            api = await llm.async_get_api(hass, 'atlas_household', ctx(call))
            result = await api.async_call_tool(llm.ToolInput(tool_name=call.data['tool'], tool_args=dict(call.data.get('args') or {})))
            return {'result': result, 'conversation_id': session.conversation_id}

    async def test_state(call):
        if call.data.get('tick'):
            await rt.coord.tick()
        rt.notify()
        rt.arm()
        api = await llm.async_get_api(hass, 'atlas_household', ctx(call))
        from voluptuous_openapi import convert  # noqa: PLC0415  (what HA's Ollama _format_tool uses)
        tools = [{'type': 'function', 'function': {'name': t.name, 'parameters': convert(t.parameters, custom_serializer=api.custom_serializer),
                  **({'description': t.description} if t.description else {})}} for t in api.tools]
        return {'data': rt.coord.data, 'api_prompt': api.api_prompt, 'tools': tools, 'ready': rt.coord.ready}

    hass.services.async_register(DOMAIN, 'test_call', test_call, schema=vol.Schema({vol.Required('tool'): str, vol.Optional('args'): dict,
                                 vol.Optional('user_text'): str, vol.Optional('last_reply'): str, vol.Required('conversation_id'): str,
                                 vol.Optional('new_turn'): bool}), supports_response=SupportsResponse.ONLY)
    hass.services.async_register(DOMAIN, 'test_state', test_state, schema=vol.Schema({vol.Optional('tick'): bool}), supports_response=SupportsResponse.ONLY)


async def _options_changed(hass, entry) -> None:
    """Only the claim-guarded agent depends on the options, so only its platform is swapped. The entry is never reloaded here: a reload
    cancels every pending timer (Codex 40 A049) [R12-10]."""
    rt = entry.runtime_data
    async with rt.options_lock:                # two quick saves never interleave unload and setup [R13-06]
        if rt.guarded_loaded:
            await hass.config_entries.async_unload_platforms(entry, ['conversation'])
            rt.guarded_loaded = False
        if (entry.options or {}).get('guarded_agent'):
            await hass.config_entries.async_forward_entry_setups(entry, ['conversation'])
            rt.guarded_loaded = True


async def async_unload_entry(hass, entry) -> bool:
    """Disable, remove or reload: every pending timer is cancelled durably (Codex 40 A049), so nothing comes back on a restart.
    (HA does not unload entries when it shuts down, so a restart keeps the queue, and start()/rebaseline() handle it.)"""
    rt = entry.runtime_data
    if getattr(rt, 'guarded_loaded', False):                # what THIS run loaded, not the (already changed) new options
        await hass.config_entries.async_unload_platforms(entry, ['conversation'])
    await rt.coord.shutdown()
    rt.notify()
    return True
