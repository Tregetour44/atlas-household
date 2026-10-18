"""TEST COPY ONLY: a streaming conversation agent with a false claim and no tool call (the C0d D60 reply)."""
from homeassistant.components import conversation
from homeassistant.const import MATCH_ALL
from homeassistant.helpers import intent

REPLY = "I have turned off the family room lights for you, but I am sorry, I cannot manage the battery settings yet."


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([StreamAgent(entry)])


class StreamAgent(conversation.ConversationEntity):
    _attr_name = 'Atlas stream test'

    def __init__(self, entry):
        self._attr_unique_id = f'{entry.entry_id}_stream'

    @property
    def supported_languages(self):
        return MATCH_ALL

    async def _async_handle_message(self, user_input, chat_log):
        async def gen():
            yield {'role': 'assistant'}
            for i in range(0, len(REPLY), 12):          # small chunks, like a model stream
                yield {'content': REPLY[i:i + 12]}

        async for _ in chat_log.async_add_delta_content_stream(self.entity_id, gen()):
            pass
        resp = intent.IntentResponse(language=user_input.language)
        resp.async_set_speech(chat_log.content[-1].content)
        return conversation.ConversationResult(response=resp, conversation_id=chat_log.conversation_id)
