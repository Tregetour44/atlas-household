"""A claim-guarded conversation agent (the lead project, within directive 0142). It forwards each turn to the underlying Atlas agent (set in the
integration's options) and then applies core.guard_reply: if the final reply claims an action that no atlas_ tool result of the SAME turn
backs, the reply is rewritten (see guard_reply). The same-turn evidence is the coordinator's own record of tool results for that
conversation since the turn started (Coordinator.evidence_since: tool and status, cloud review 1 M8). Nothing here can act: it only rewrites words.
  - While the underlying agent runs, the chat log's delta listener is detached, so nothing streams to TTS or to the client before the guard
    has read the whole reply; the pipeline then speaks the final (possibly rewritten) speech [R12-01].
  - A rewrite is written back into the chat log, so the model's history and the yes-check (last_reply) see what was said [R12-03].
  - English only: the guard reads English, so another language is refused rather than passed unguarded [R12-11].
  - A strict timer request naming exactly one light or scene ("study lights off in 10 minutes", "porch lights on at 7") is scheduled by the
    coordinator directly, never through the model (fastpath.py); everything else goes to the model.
  - If the first reply claims something and NO tool ran in the turn, the model is asked once to call the tool or say it can't; the second
    reply is guarded the same way (C0e triage 1). Never more than one extra ask; never when any tool ran.
Not created unless an underlying agent is configured. HA imports only inside this file (it loads only inside HA).
"""
from __future__ import annotations

import dataclasses

from homeassistant.components import conversation
from homeassistant.components.conversation.chat_log import AssistantContent, ToolResultContent, UserContent
from homeassistant.const import MATCH_ALL
from homeassistant.helpers import intent

from types import SimpleNamespace

from .core import guard_reply
from .turn import NUDGE, run_turn


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    agent = (entry.options or {}).get('guarded_agent')
    if agent:
        async_add_entities([AtlasGuardedAgent(entry, agent)])


def _refuse(user_input, chat_log, text):
    resp = intent.IntentResponse(language=user_input.language)
    resp.async_set_error(intent.IntentResponseErrorCode.UNKNOWN, text)
    return conversation.ConversationResult(response=resp, conversation_id=chat_log.conversation_id)


class AtlasGuardedAgent(conversation.ConversationEntity):
    _attr_has_entity_name = True
    _attr_name = 'Atlas (claim-guarded)'

    def __init__(self, entry, agent_id: str) -> None:
        self._entry, self._agent = entry, agent_id
        self._attr_unique_id = f'{entry.entry_id}_claim_guarded'

    @property
    def supported_languages(self):
        return MATCH_ALL            # selectable in any pipeline; a non-English turn is refused below, never passed unguarded

    async def _async_handle_message(self, user_input: conversation.ConversationInput, chat_log) -> conversation.ConversationResult:
        rt = self._entry.runtime_data
        if not (user_input.language or 'en').lower().startswith('en'):
            return _refuse(user_input, chat_log, 'Atlas (claim-guarded) works in English only.')
        if self._agent == self.entity_id:
            return _refuse(user_input, chat_log, "Atlas (claim-guarded) isn't set up correctly: it points at itself.")
        n0 = len(chat_log.content)
        last = {}

        async def ask(text):
            listener, chat_log.delta_listener = chat_log.delta_listener, None
            try:
                last['result'] = await conversation.async_converse(self.hass, text, chat_log.conversation_id, user_input.context,
                                                                   user_input.language, agent_id=self._agent, device_id=user_input.device_id,
                                                                   satellite_id=user_input.satellite_id,
                                                                   extra_system_prompt=user_input.extra_system_prompt)
            finally:
                chat_log.delta_listener = listener
            return ((last['result'].response.speech or {}).get('plain') or {}).get('speech', '')

        def other_tools():
            return any(isinstance(c, ToolResultContent) and not str(c.tool_name).startswith('atlas_') for c in chat_log.content[n0:])

        async def call_tool(name, args):          # the fast path's call carries the person's context, like a model tool call
            return await rt.call(name, args, chat_log.conversation_id, user_input.text, None, None, SimpleNamespace(context=user_input.context))

        # one turn, in the order the household hears it (turn.run_turn; the Atlas-side project's runners call the same function)
        out = await run_turn(rt.coord, user_input.text, chat_log.conversation_id, ask, other_tools=other_tools, call_tool=call_tool)
        if out['path'] == 'fast':
            speech = out['reply']
            chat_log.async_add_assistant_content_without_tools(AssistantContent(agent_id=self.entity_id, content=speech))
            resp = intent.IntentResponse(language=user_input.language)
            resp.async_set_speech(speech)
            return conversation.ConversationResult(response=resp, conversation_id=chat_log.conversation_id,
                                                   continue_conversation=speech.rstrip().endswith('?'))
        result, new, bad, statuses = last['result'], out['reply'], out['claims'], out.get('evidence', out['statuses'])   # (tool, status) pairs [M8]
        if out['path'] == 'nudged':          # [B16-02] drop the nudge message and the unspoken first reply (its tool-free text) from the history
            k = next((i for i in range(n0, len(chat_log.content)) if isinstance(chat_log.content[i], UserContent) and chat_log.content[i].content == NUDGE), None)
            if k is not None:
                drop = {k} | {i for i in range(n0, k) if isinstance(chat_log.content[i], AssistantContent) and not chat_log.content[i].tool_calls}
                chat_log.content[:] = [c for i, c in enumerate(chat_log.content) if i not in drop]
        if new != (((result.response.speech or {}).get('plain') or {}).get('speech', '')):
            result.response.async_set_speech(new)
            result.continue_conversation = new.rstrip().endswith('?')       # the dropped text may have been the question
        said = [i for i in range(n0, len(chat_log.content)) if isinstance(chat_log.content[i], AssistantContent) and chat_log.content[i].content]
        for i in said:                     # the history holds what was said: the final text as spoken, earlier text guarded the same way
            c = chat_log.content[i]
            text = new if i == said[-1] else guard_reply(c.content, statuses)[0]
            if text != c.content:
                chat_log.content[i] = dataclasses.replace(c, content=text, native=None, thinking_content=None)   # native data indexes the original
        return result
