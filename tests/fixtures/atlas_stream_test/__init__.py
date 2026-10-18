"""TEST COPY ONLY (R12-01 evidence). Copied into the test copy by tests/run_testcopy.py; never shipped, never in the household HA.

- conversation.atlas_stream_test: a conversation agent that STREAMS its reply into the chat log the way HA's LLM integrations do
  (chat_log.async_add_delta_content_stream), with a long false claim and no tool call (the D60 reply).
- atlas_stream_test.pcloset: runs one turn the way the Assist pipeline does (assist_pipeline/pipeline.py 1221-1306 in HA 2026.8): it opens the
  chat session and chat log WITH a delta listener, then calls ha_conv.async_converse. It returns every delta the listener saw (what a
  streaming TTS engine and the client would have received), the final speech, and the assistant texts left in the chat log.
"""
from homeassistant.components import conversation as ha_conv   # not "conversation": this package has its own conversation.py
from homeassistant.core import SupportsResponse
from homeassistant.helpers import chat_session

DOMAIN = 'atlas_stream_test'


async def async_setup_entry(hass, entry):
    if hass.config.location_name != 'Atlas test copy':
        return False
    import voluptuous as vol  # noqa: PLC0415

    async def pcloset(call):
        deltas = []

        def listener(chat_log, delta):
            deltas.append(delta)

        cid = call.data['conversation_id']
        user_input = ha_conv.ConversationInput(text=call.data['text'], context=call.context, conversation_id=cid, device_id=None,
                                                    satellite_id=None, language='en', agent_id=call.data['agent_id'])
        with chat_session.async_get_chat_session(hass, cid) as session, \
                ha_conv.async_get_chat_log(hass, session, user_input, chat_log_delta_listener=listener) as chat_log:
            result = await ha_conv.async_converse(hass=hass, text=user_input.text, conversation_id=cid, context=call.context,
                                                       language='en', agent_id=call.data['agent_id'])
            said = [c.content for c in chat_log.content if isinstance(c, ha_conv.AssistantContent) and c.content]
        return {'deltas': [d.get('content') for d in deltas if d.get('content')],
                'speech': result.response.speech.get('plain', {}).get('speech', ''), 'history': said}

    hass.services.async_register(DOMAIN, 'pcloset', pcloset, schema=vol.Schema({vol.Required('text'): str, vol.Required('conversation_id'): str,
                                 vol.Required('agent_id'): str}), supports_response=SupportsResponse.ONLY)
    await hass.config_entries.async_forward_entry_setups(entry, ['conversation'])
    return True


async def async_unload_entry(hass, entry):
    hass.services.async_remove(DOMAIN, 'pcloset')
    return await hass.config_entries.async_unload_platforms(entry, ['conversation'])
