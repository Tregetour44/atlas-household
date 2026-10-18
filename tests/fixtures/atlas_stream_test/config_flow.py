"""TEST COPY ONLY: one entry, no options."""
from homeassistant.config_entries import ConfigFlow


class StreamTestFlow(ConfigFlow, domain='atlas_stream_test'):
    async def async_step_user(self, user_input=None):
        return self.async_create_entry(title='Atlas stream test', data={})
