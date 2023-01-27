import math
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
            self._attr_native_value = self._calculate_tank_level(self._device.dsn,                self.coordinator.data[self._device.dsn][PROPERTY_TANK_LEVEL]
            )
        self.async_write_ha_state()

    def _calculate_tank_level(self, dsn, distance) -> float:
        distance /= 10
        tank_shape = self._coordinator._device_data[dsn]["TankShape"]
        tank_width = int(self._coordinator._device_data[dsn]["TankWidth"])
        tank_length = int(self._coordinator._device_data[dsn]["TankLength"])
        tank_height = int(self._coordinator._device_data[dsn]["TankHeight"])
        tank_manifolds = int(self._coordinator._device_data[dsn]["TankManifold"])
        match tank_shape:
            case "Rectangle":
                result = self._calculate_rectangle_tank_level(
                    tank_height, tank_length, tank_width, distance
                )
            case "Vertical_Obround":
                result = self._calculate_vertical_obround_tank_level(
                    tank_height, tank_length, tank_width, distance
                )
            case "Horizontal_Obround":
                result = self._calculate_horizontal_obround_tank_level(
                    tank_height, tank_length, tank_width, distance
                )
            case "Vertical_Cylinder":
                result = self._calculate_vertical_cylinder_tank_level(
                    tank_height, tank_width, distance
                )
            case "Horizontal_Cylinder":
                result = self._calculate_horizontal_cylinder_tank_level(
                    tank_height, tank_length, distance
                )
            case "Granby":
                result = self._calculate_granby_tank_level(
                    tank_height, tank_length, tank_width, distance
                )
        return round((result * tank_manifolds) / 231,2)


    def _calculate_rectangle_tank_level(self, height, width, length, distance) -> float:
        return length * width * min(max(height + 3.565 - distance, 0), height)

    def _calculate_vertical_cylinder_tank_level(self, height, width, distance) -> float:
        mid_width = width / 2
        measurement = min(max(height + 1.37 - distance, 0), height)
        return math.pi * measurement * (mid_width**2)

    def _calculate_horizontal_cylinder_tank_level(
        self, height, length, distance
    ) -> float:
        mid_height = height / 2
        measurement = min(max(height + 1.37 - distance, 0), height)


        return length * (
            (mid_height**2) * math.acos((mid_height - measurement) / mid_height)
            - (mid_height - measurement)
            * math.sqrt(2 * mid_height * measurement - (measurement**2))
        )

    def _calculate_horizontal_obround_tank_level(
        self, height, length, width, distance
    ) -> float:
        mid_height = height / 2
        width_height_diff = width - height
        calculation = min(max(height + 1.37 - distance, 0), height)
        return (
            length
            * (
                mid_height
                * mid_height
                * math.acos((mid_height - calculation) / mid_height)
                - (mid_height - calculation)
                * math.sqrt(2 * mid_height * calculation - calculation**2)
            )
            + length * width_height_diff * calculation
        )

    def _calculate_vertical_obround_tank_level(
        self, height, length, width, distance
    ) -> float:
        mid_width = width / 2
        height_width_diff = height - width
        calculation = min(max(height + 1.37 - distance, 0), height)
        measurement = 0
        multiplier = 0
        if calculation < mid_width:
            measurement = calculation
            multiplier = 0
        else:
            if calculation < height_width_diff + mid_width:
                measurement = mid_width
                multiplier = calculation - mid_width
            else:
                measurement = calculation - height_width_diff
                multiplier = height_width_diff
        return (
            length
            * (
                mid_width**2 * math.acos((mid_width - measurement) / mid_width)
                - (mid_width - measurement)
                * math.sqrt(2 * mid_width * measurement - measurement**2)
            )
            + length * width * multiplier
        )

    def _calculate_granby_tank_level(self, height, length, width, distance) -> float:
        calculation1 = 0
        calculation2 = 0
        mid_width = width / 2
        length_point = 0.215 * length
        width_point = 0.375 * width
        height_width_diff = height - 2 * width_point
        length_offset = length - 2 * length_point
        distance_from_top = min(max(height - distance, 0), height)
        if distance_from_top < width_point:
            calculation1 = distance_from_top
            calculation2 = 0
        else:
            if distance_from_top < height_width_diff + width_point:
                calculation1 = width_point
                calculation2 = distance_from_top - width_point
            else:
                calculation1 = distance_from_top - height_width_diff
                calculation2 = height_width_diff
        radial_measurement = math.pi * mid_width * length_point * calculation2
        volumetric_calculation1 = length_offset * (
            mid_width
            * width_point
            * math.acos((width_point - calculation1) / width_point)
            - (width_point - calculation1)
            * math.sqrt(2 * width_point * calculation1 - calculation1 * calculation1)
        )

        volumetric_calculation2 = (
            (3 * width_point - calculation1)
            * (math.pi * mid_width * length_point * calculation1**2)
        ) / (3 * width_point**2)
        volumetric_calculation3 = length_offset * width * calculation2

        return max(
            radial_measurement
            + volumetric_calculation1
            + volumetric_calculation2
            + volumetric_calculation3
            + -808.5,
            0,
        )