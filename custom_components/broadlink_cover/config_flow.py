import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from .const import DOMAIN

class BroadlinkCoverConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            return self.async_create_entry(
                title=user_input["name"],
                data=user_input,
            )

        data_schema = vol.Schema(
            {
                vol.Required("name"): str,
                vol.Required("remote_entity_id"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="remote")
                ),
                vol.Required("device"): str,
                vol.Required("open"): str,
                vol.Required("stop"): str,
                vol.Required("close"): str,
                vol.Optional("open_time", default=35): int,
                vol.Optional("close_time", default=34): int,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
