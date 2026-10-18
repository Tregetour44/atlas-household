"""Config flow: one entry, which names the allowed-target map file shipped beside this code (targets*.json). Nothing else is configurable."""
from __future__ import annotations

import pathlib

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

DOMAIN = 'atlas_household'
HERE = pathlib.Path(__file__).parent


class AtlasConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        maps = sorted((p.name for p in await self.hass.async_add_executor_job(lambda: list(HERE.glob('targets*.json')))),
                      key=lambda n: (n != 'targets.json', n))     # the household map first; the demo map exists only where the test installer put it
        if not maps:
            return self.async_abort(reason='no_target_map')
        if user_input is not None:
            return self.async_create_entry(title='Atlas household coordinator', data={'targets': user_input['targets']})
        return self.async_show_form(step_id='user', data_schema=vol.Schema({vol.Required('targets', default=maps[0]): vol.In(maps)}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AtlasOptionsFlow()


class AtlasOptionsFlow(OptionsFlow):
    """One option: the underlying Atlas agent that the claim-guarded agent forwards to (empty = no guarded agent)."""

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            agent = (user_input.get('guarded_agent') or '').strip()
            err = self._check(agent) if agent else None
            if err:
                return self.async_show_form(step_id='init', errors={'guarded_agent': err},
                                            data_schema=vol.Schema({vol.Optional('guarded_agent', default=agent): str}))
            return self.async_create_entry(data={'guarded_agent': agent})
        cur = (self.config_entry.options or {}).get('guarded_agent', '')
        return self.async_show_form(step_id='init', data_schema=vol.Schema({vol.Optional('guarded_agent', default=cur): str}))

    def _check(self, agent: str) -> str | None:
        """The underlying agent must be an existing conversation agent, not this one, and not HA's built-in agent (which acts by itself)
        except on the test copy, whose checks use it [R12-06, R12-09]. It should be an Atlas-only agent (its only tools the atlas_ ones);
        if another tool runs in a turn, the guard never says "I haven't changed anything" (conversation.py, external_tool) [R13-06]."""
        from homeassistant.helpers import entity_registry as er  # noqa: PLC0415
        from . import guarded_platform_available  # noqa: PLC0415
        if not guarded_platform_available():
            return 'guard_not_installed'          # this copy doesn't ship the guarded agent [cloud review 1, M1]
        own = er.async_get(self.hass).async_get_entity_id('conversation', DOMAIN, f'{self.config_entry.entry_id}_claim_guarded')
        if not agent.startswith('conversation.') or self.hass.states.get(agent) is None:
            return 'not_a_conversation_agent'
        if agent == own:
            return 'points_at_itself'
        from . import TEST_COPY_NAME  # noqa: PLC0415
        if agent == 'conversation.home_assistant' and self.hass.config.location_name != TEST_COPY_NAME:
            return 'acts_by_itself'
        return None
