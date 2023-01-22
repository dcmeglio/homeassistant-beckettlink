"""Config flow for Beckettlink integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.httpx_client import get_async_client
import homeassistant.helpers.config_validation as cv

from aioayla import AylaApi, AylaAccessError

from .const import APP_ID, APP_SECRET, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Beckettlink."""

    def __init__(self):
        """Initialize the config flow."""
        self._api = AylaApi(APP_ID, APP_SECRET, get_async_client(self.hass))
        self._sensors = {}
        self.data = None

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            if await self._api.login(user_input["username"], user_input["password"]):
                device_data = await self._api.get_devices()
                self._sensors = {
                    dev.dsn: dev.product_name
                    for dev in device_data
                    if dev.device_type == "Node"
                }
                self.data = user_input
                return await self.async_step_devices()
            else:
                errors["base"] = "invalid_auth"
        except AylaAccessError:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_devices(self, user_input: dict[str, Any] | None = None):
        """Handle sensor selection step."""
        if user_input is None:
            return self.async_show_form(
                step_id="devices",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            "sensors", default=list(self._sensors)
                        ): cv.multi_select(self._sensors)
                    }
                ),
            )
        else:
            self.data.update(user_input)
            return self.async_create_entry(
                title=self.data[CONF_USERNAME], data=self.data
            )
