"""The Beckettlink integration."""
from __future__ import annotations
import asyncio
from datetime import timedelta
import logging

from aioayla import AylaApi, AylaAccessError, AylaDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.httpx_client import get_async_client

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import APP_ID, APP_SECRET, DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Beckettlink from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    client = AylaApi(APP_ID, APP_SECRET, get_async_client(hass))
    try:
        await client.login(entry.data.get(CONF_USERNAME), entry.data.get(CONF_PASSWORD))
    except Exception as ex:
        raise ConfigEntryNotReady() from ex

    coordinator = BeckettlinkCoordinator(hass, client, entry)

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await coordinator.async_config_entry_first_refresh()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class BeckettlinkCoordinator(DataUpdateCoordinator):
    """Beckettlink coordinator."""

    def __init__(
        self, hass: HomeAssistant, api: AylaApi, entry: ConfigEntry, devices=None
    ):
        """Initialize Beckettlink coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="BeckettLink",
            update_interval=timedelta(hours=2),
        )
        self.api: AylaApi = api
        self.hass: HomeAssistant = hass
        self.entry = entry
        self._device_properties: dict[str, dict[str, str]] = {}
        self._device_data: dict[str, dict[str, str]] = {}
        self._sensors: AylaDevice = None
        self._device_lock = asyncio.Lock()

    async def get_sensors(self):
        """Get a list of device sensors."""
        async with self._device_lock:
            if self._sensors is None:
                try:
                    device_data = await self.api.get_devices()

                    self._sensors = [
                        dev for dev in device_data if dev.device_type == "Node"
                    ]

                    for sensor in self._sensors:
                        properties = await sensor.get_properties()
                        self._device_properties[sensor.dsn] = properties
                        data = await sensor.get_data()
                        self._device_data[sensor.dsn] = data
                except AylaAccessError:
                    await self.entry.async_start_reauth(self.hass)
            return self._sensors

    def get_sensor_properties(self, sensor_id: str) -> dict[str, str]:
        """Retrieve the properties for a given sensor."""
        if sensor_id in self._device_properties:
            return self._device_properties[sensor_id]
        else:
            return {}

    def get_sensor_data(self, sensor_id: str) -> dict[str, str]:
        """Retrieve the data for a given sensor."""
        if sensor_id in self._device_properties:
            return self._device_data[sensor_id]
        else:
            return {}

    async def _async_update_data(self) -> dict[str, dict[str, str]]:
        """Fetch data from API endpoint."""
        result = {}
        for sensor in await self.get_sensors():
            try:
                properties = await sensor.get_properties()
                result[sensor.dsn] = properties
            except AylaAccessError as aex:
                raise ConfigEntryAuthFailed() from aex
            except Exception as ex:
                raise UpdateFailed() from ex
        return result
