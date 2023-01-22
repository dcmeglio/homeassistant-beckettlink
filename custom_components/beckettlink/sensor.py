from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS, UnitOfVolume

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BeckettlinkCoordinator
from .const import (
    DOMAIN,
    MANUFACTURER,
    PROPERTY_BATTERY_LIFE,
    PROPERTY_FIRMWARE_VERSION,
    PROPERTY_HARDWARE_VERSION,
    PROPERTY_SIGNAL_STRENGTH,
    PROPERTY_TANK_LEVEL,
)

from aioayla import AylaDevice


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry, add_entities):
    """Setup the Beckettlink sensors."""
    coordinator: BeckettlinkCoordinator = hass.data[DOMAIN][config.entry_id]
    sensors = None

    try:
        sensors = await coordinator.get_sensors()
    except Exception as ex:
        raise ConfigEntryNotReady("Failed to retrieve BeckettLink devices") from ex

    entities = []
    for sensor in sensors:
        entities.append(
            BeckettLinkTankSensorEntity(
                hass=hass,
                name="Battery Level",
                device_class="battery",
                device_type="battery",
                device=sensor,
                coordinator=coordinator,
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        )
        entities.append(
            BeckettLinkTankSensorEntity(
                hass=hass,
                name="Tank Level",
                device_class=None,
                device_type="tank_level",
                device=sensor,
                coordinator=coordinator,
                entity_category=None,
            )
        )
        entities.append(
            BeckettLinkTankSensorEntity(
                hass=hass,
                name="Signal Strength",
                device_type="signal_strength",
                device=sensor,
                coordinator=coordinator,
                device_class="signal_strength",
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        )

    add_entities(entities)


class BeckettLinkTankSensorEntity(SensorEntity, CoordinatorEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        device_type: str,
        device: AylaDevice,
        coordinator: BeckettlinkCoordinator,
        device_class: str,
        entity_category: EntityCategory,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_has_entity_name = True
        self._coordinator = coordinator
        self._device = device

        self._device_type = device_type
        self._attr_entity_category = entity_category
        self._attr_unique_id = device.dsn + "_" + device_type

        if device_type == "signal_strength":
            self._attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS
        elif device_type == "battery":
            self._attr_native_unit_of_measurement = PERCENTAGE
        elif device_type == "tank_level":
            self._attr_native_unit_of_measurement = UnitOfVolume.GALLONS
            self._attr_icon = "mdi:hydraulic-oil-level"

        properties = coordinator.get_sensor_properties(device.dsn)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.dsn)},
            manufacturer=MANUFACTURER,
            name=device.product_name,
            model=device.manuf_model,
            sw_version=properties[PROPERTY_FIRMWARE_VERSION],
            hw_version=properties[PROPERTY_HARDWARE_VERSION],
        )

    def _handle_coordinator_update(self) -> None:
        if self._device_type == "battery":
            self._attr_native_value = self.coordinator.data[self._device.dsn][
                PROPERTY_BATTERY_LIFE
            ]
        elif self._device_type == "signal_strength":
            self._attr_native_value = self.coordinator.data[self._device.dsn][
                PROPERTY_SIGNAL_STRENGTH
            ]
        elif self._device_type == "tank_level":
            self._attr_native_value = self.coordinator.data[self._device.dsn][
                PROPERTY_TANK_LEVEL
            ]
        self.async_write_ha_state()
