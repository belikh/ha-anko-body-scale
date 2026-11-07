"""Sensor platform for the ANKO Body Scale integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfMass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import AnkoScaleCoordinator
from .const import DOMAIN

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AnkoScaleSensorDescription(SensorEntityDescription):
    """Describes an ANKO Body Scale sensor entity."""

    value_fn: Callable[[AnkoScaleCoordinator], float | None]
    available_fn: Callable[[AnkoScaleCoordinator], bool] = lambda c: (
        c.reading is not None
    )


SENSOR_DESCRIPTIONS: tuple[AnkoScaleSensorDescription, ...] = (
    AnkoScaleSensorDescription(
        key="weight",
        translation_key="weight",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda c: c.reading.weight_kg if c.reading else None,
    ),
    AnkoScaleSensorDescription(
        key="impedance",
        translation_key="impedance",
        native_unit_of_measurement="Ω",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
        value_fn=lambda c: c.reading.impedance_ohm if c.reading else None,
    ),
    AnkoScaleSensorDescription(
        key="bmi",
        translation_key="bmi",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        available_fn=lambda c: bool(c.metrics),
        value_fn=lambda c: c.metrics.get("bmi"),
    ),
    AnkoScaleSensorDescription(
        key="body_fat_percent",
        translation_key="body_fat_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        available_fn=lambda c: bool(c.metrics),
        value_fn=lambda c: c.metrics.get("body_fat_percent"),
    ),
    AnkoScaleSensorDescription(
        key="fat_mass",
        translation_key="fat_mass",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        available_fn=lambda c: bool(c.metrics),
        value_fn=lambda c: c.metrics.get("fat_mass_kg"),
    ),
    AnkoScaleSensorDescription(
        key="lean_mass",
        translation_key="lean_mass",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        available_fn=lambda c: bool(c.metrics),
        value_fn=lambda c: c.metrics.get("lean_mass_kg"),
    ),
    AnkoScaleSensorDescription(
        key="muscle_mass",
        translation_key="muscle_mass",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        available_fn=lambda c: bool(c.metrics),
        value_fn=lambda c: c.metrics.get("muscle_mass_kg"),
    ),
    AnkoScaleSensorDescription(
        key="body_water",
        translation_key="body_water",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        available_fn=lambda c: bool(c.metrics),
        value_fn=lambda c: c.metrics.get("body_water_percent"),
    ),
    AnkoScaleSensorDescription(
        key="bone_mass",
        translation_key="bone_mass",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        available_fn=lambda c: bool(c.metrics),
        value_fn=lambda c: c.metrics.get("bone_mass_kg"),
    ),
    AnkoScaleSensorDescription(
        key="bmr",
        translation_key="bmr",
        native_unit_of_measurement="kcal/d",
        state_class=SensorStateClass.MEASUREMENT,
        available_fn=lambda c: bool(c.metrics),
        value_fn=lambda c: c.metrics.get("bmr"),
    ),
    AnkoScaleSensorDescription(
        key="metabolic_age",
        translation_key="metabolic_age",
        native_unit_of_measurement="yr",
        state_class=SensorStateClass.MEASUREMENT,
        available_fn=lambda c: bool(c.metrics),
        value_fn=lambda c: c.metrics.get("metabolic_age"),
    ),
    AnkoScaleSensorDescription(
        key="visceral_fat_index",
        translation_key="visceral_fat_index",
        state_class=SensorStateClass.MEASUREMENT,
        available_fn=lambda c: bool(c.metrics),
        value_fn=lambda c: c.metrics.get("visceral_fat_index"),
    ),
    AnkoScaleSensorDescription(
        key="ideal_weight_min",
        translation_key="ideal_weight_min",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        available_fn=lambda c: bool(c.metrics),
        value_fn=lambda c: c.metrics.get("ideal_weight_min_kg"),
    ),
    AnkoScaleSensorDescription(
        key="ideal_weight_max",
        translation_key="ideal_weight_max",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        available_fn=lambda c: bool(c.metrics),
        value_fn=lambda c: c.metrics.get("ideal_weight_max_kg"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up ANKO Body Scale sensors from a config entry."""
    coordinator: AnkoScaleCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AnkoScaleSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    )


class AnkoScaleSensor(SensorEntity, RestoreEntity):
    """A single body-composition measurement from the ANKO scale."""

    _attr_has_entity_name = True
    entity_description: AnkoScaleSensorDescription

    def __init__(
        self, coordinator: AnkoScaleCoordinator, description: AnkoScaleSensorDescription
    ) -> None:
        """Initialise the sensor from its description and coordinator."""
        self.entity_description = description
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.address}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            name="ANKO Body Scale",
            manufacturer="ANKO",
            model="iF1012D",
        )
        self._restored_value: float | None = None

    @property
    def native_value(self) -> float | None:
        """Return the current measurement, falling back to restored state."""
        value = self.entity_description.value_fn(self._coordinator)
        return value if value is not None else self._restored_value

    @property
    def available(self) -> bool:
        """Return whether this measurement is available."""
        if self.entity_description.available_fn(self._coordinator):
            return True
        return self._restored_value is not None

    async def async_added_to_hass(self) -> None:
        """Restore the last state and subscribe to new readings."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in (
            "unknown",
            "unavailable",
        ):
            try:
                self._restored_value = float(last_state.state)
            except ValueError:
                self._restored_value = None
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )
