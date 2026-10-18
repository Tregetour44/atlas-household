"""HA wiring for the coordinator: the backend that talks to hass, the LLM API ("Atlas household") and its tools, built from tools.py SPECS.
Imported only by __init__.async_setup_entry (inside HA), so core/tools/fake stay importable without Home Assistant.
"""
from __future__ import annotations

import asyncio
import time

import voluptuous as vol

from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm

from .tools import API_ID, API_NAME, api_prompt, specs


class HABackend:
    """The only place the coordinator reaches the house: state reads, one service call per send (blocking), and read-back polling."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.context: Context | None = None

    async def get_state(self, entity_id):
        st = self.hass.states.get(entity_id)
        return None if st is None else {'entity_id': entity_id, 'state': st.state, 'attributes': dict(st.attributes), 'last_changed': st.last_changed.isoformat()}

    async def call(self, domain, service, entity_ids, data):
        await self.hass.services.async_call(domain, service, {'entity_id': list(entity_ids), **data}, blocking=True, context=self.context)

    async def wait_for(self, entity_id, predicate, timeout):
        end = time.monotonic() + timeout
        st = await self.get_state(entity_id)
        while not predicate(st) and time.monotonic() < end:
            await asyncio.sleep(0.25)
            st = await self.get_state(entity_id)
        return st


def _vol_schema(props: dict, required: list) -> vol.Schema:
    out = {}
    for k, p in props.items():
        key = (vol.Required if k in required else vol.Optional)(k, description=p['description']) if 'description' in p else \
              (vol.Required if k in required else vol.Optional)(k)
        if p['type'] == 'string':
            val = vol.In(p['enum']) if 'enum' in p else str
        else:
            val = vol.All(int, vol.Range(min=p['minimum'], max=p['maximum']))
        out[key] = val
    return vol.Schema(out)


class AtlasTool(llm.Tool):
    def __init__(self, runtime, name: str, description: str, props: dict, required: list) -> None:
        self.runtime, self.name, self.description = runtime, name, description
        self.parameters = _vol_schema(props, required)

    async def async_call(self, hass: HomeAssistant, tool_input: llm.ToolInput, llm_context: llm.LLMContext):
        # The person's own words this turn, for the plain-yes check (never a flag from the model) and the conversation id.
        from homeassistant.components.conversation.chat_log import AssistantContent, UserContent, current_chat_log  # noqa: PLC0415
        chat = current_chat_log.get()
        user_text, conversation_id, turn, last_reply = '', None, None, None
        if chat is not None:
            conversation_id = chat.conversation_id
            content = list(chat.content)
            for i in range(len(content) - 1, -1, -1):
                if isinstance(content[i], UserContent):
                    c = content[i]
                    user_text, turn = c.content, f'{i}:{c.created.isoformat()}'   # this user turn's identity
                    for j in range(i - 1, -1, -1):                                  # Atlas's reply just before it (for the yes check)
                        if isinstance(content[j], AssistantContent) and content[j].content:
                            last_reply = content[j].content
                            break
                        if isinstance(content[j], UserContent):
                            break
                    break
        return await self.runtime.call(tool_input.tool_name, dict(tool_input.tool_args), conversation_id, user_text, turn, last_reply,
                                       llm_context, tool_input.id)


class AtlasAPI(llm.API):
    def __init__(self, hass: HomeAssistant, runtime) -> None:
        super().__init__(hass=hass, id=API_ID, name=API_NAME)
        self.runtime = runtime

    async def async_get_api_instance(self, llm_context: llm.LLMContext) -> llm.APIInstance:
        handles = self.runtime.coord.handles
        tools = [AtlasTool(self.runtime, n, d, p, r) for n, d, p, r in specs(handles, self.runtime.coord.timer_blinds)]
        return llm.APIInstance(api=self, api_prompt=api_prompt(handles), llm_context=llm_context, tools=tools)
