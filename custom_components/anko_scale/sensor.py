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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .attribution import PersonProfile
from .const import DOMAIN, PERSON_UNIQUE_PREFIX
from .coordinator import AnkoScaleCoordinator
from .entity import person_device_info, scale_device_info
from .people import HUB_KEY, PeopleHub, PersonState, is_people_entry

PARALLEL_UPDATES = 0

# Scale-level sensors. Body composition lives on the person devices.
SCALE_SENSOR_KEYS = frozenset({"weight", "impedance"})


def _has_metrics(state: PersonState) -> bool:
    return bool(state.metrics)


def _has_weight(state: PersonState) -> bool:
    return state.weight_kg is not None


@dataclass(frozen=True, kw_only=True)
class AnkoScaleSensorDescription(SensorEntityDescription):
    """Describes an ANKO Body Scale sensor entity."""

    value_fn: Callable[[PersonState], float | None]
    available_fn: Callable[[PersonState], bool] = _has_weight


SENSOR_DESCRIPTIONS: tuple[AnkoScaleSensorDescription, ...] = (
    AnkoScaleSensorDescription(
        key="weight",
        translation_key="weight",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda s: s.weight_kg,
    ),
    AnkoScaleSensorDescription(
        key="impedance",
        translation_key="impedance",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=0,
        value_fn=lambda s: s.impedance_raw,
    ),
    AnkoScaleSensorDescription(
        key="bmi",
        translation_key="bmi",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        available_fn=_has_metrics,
        value_fn=lambda s: s.metrics.get("bmi"),
    ),
    AnkoScaleSensorDescription(
        key="body_fat_percent",
        translation_key="body_fat_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        available_fn=_has_metrics,
        value_fn=lambda s: s.metrics.get("body_fat_percent"),
    ),
    AnkoScaleSensorDescription(
        key="fat_mass",
        translation_key="fat_mass",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        available_fn=_has_metrics,
        value_fn=lambda s: s.metrics.get("fat_mass_kg"),
    ),
    AnkoScaleSensorDescription(
        key="lean_mass",
        translation_key="lean_mass",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        available_fn=_has_metrics,
        value_fn=lambda s: s.metrics.get("lean_mass_kg"),
    ),
    AnkoScaleSensorDescription(
        key="muscle_mass",
        translation_key="muscle_mass",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        available_fn=_has_metrics,
        value_fn=lambda s: s.metrics.get("muscle_mass_kg"),
    ),
    AnkoScaleSensorDescription(
        key="body_water",
        translation_key="body_water",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        available_fn=_has_metrics,
        value_fn=lambda s: s.metrics.get("body_water_percent"),
    ),
    AnkoScaleSensorDescription(
        key="bone_mass",
        translation_key="bone_mass",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        available_fn=_has_metrics,
        value_fn=lambda s: s.metrics.get("bone_mass_kg"),
    ),
    AnkoScaleSensorDescription(
        key="bmr",
        translation_key="bmr",
        native_unit_of_measurement="kcal/d",
        state_class=SensorStateClass.MEASUREMENT,
        available_fn=_has_metrics,
        value_fn=lambda s: s.metrics.get("bmr"),
    ),
    AnkoScaleSensorDescription(
        key="metabolic_age",
        translation_key="metabolic_age",
        native_unit_of_measurement="yr",
        state_class=SensorStateClass.MEASUREMENT,
        available_fn=_has_metrics,
        value_fn=lambda s: s.metrics.get("metabolic_age"),
    ),
    AnkoScaleSensorDescription(
        key="visceral_fat_index",
        translation_key="visceral_fat_index",
        state_class=SensorStateClass.MEASUREMENT,
        available_fn=_has_metrics,
        value_fn=lambda s: s.metrics.get("visceral_fat_index"),
    ),
    AnkoScaleSensorDescription(
        key="ideal_weight_min",
        translation_key="ideal_weight_min",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        available_fn=_has_metrics,
        value_fn=lambda s: s.metrics.get("ideal_weight_min_kg"),
    ),
    AnkoScaleSensorDescription(
        key="ideal_weight_max",
        translation_key="ideal_weight_max",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        available_fn=_has_metrics,
        value_fn=lambda s: s.metrics.get("ideal_weight_max_kg"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up ANKO Body Scale sensors from a config entry."""
    if is_people_entry(entry):
        hub = hass.data[HUB_KEY]
        async_add_entities(
            AnkoScalePersonSensor(hub, profile, description)
            for profile in hub.persons
            for description in SENSOR_DESCRIPTIONS
        )
        return

    coordinator: AnkoScaleCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        AnkoScaleSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
        if description.key in SCALE_SENSOR_KEYS
    ]
    entities.append(AnkoScaleLastPersonSensor(coordinator))
    entities.append(AnkoScalePendingCountSensor(coordinator))
    async_add_entities(entities)


class _AnkoRestoreSensor(SensorEntity, RestoreEntity):
    """Numeric sensor that restores its last value across restarts."""

    _attr_has_entity_name = True
    entity_description: AnkoScaleSensorDescription

    def __init__(
        self,
        source: AnkoScaleCoordinator | PeopleHub,
        description: AnkoScaleSensorDescription,
    ) -> None:
        """Initialise from a description and the object that notifies changes."""
        self.entity_description = description
        self._source = source
        self._restored_value: float | None = None

    def _snapshot(self) -> PersonState:
        raise NotImplementedError

    @property
    def native_value(self) -> float | None:
        """Return the current measurement, falling back to restored state."""
        value = self.entity_description.value_fn(self._snapshot())
        return value if value is not None else self._restored_value

    @property
    def available(self) -> bool:
        """Return whether this measurement is available."""
        if self.entity_description.available_fn(self._snapshot()):
            return True
        return self._restored_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Say whether body composition came from impedance or from BMI."""
        metrics = self._snapshot().metrics
        if "bia_valid" not in metrics or self.entity_description.key in (
            "weight",
            "impedance",
        ):
            return None
        return {"method": "bia_assumed" if metrics["bia_valid"] else "bmi"}

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
        self.async_on_remove(self._source.async_add_listener(self.async_write_ha_state))


class AnkoScaleSensor(_AnkoRestoreSensor):
    """A scale-level reading: raw weight or impedance code of the latest advert."""

    def __init__(
        self, coordinator: AnkoScaleCoordinator, description: AnkoScaleSensorDescription
    ) -> None:
        """Initialise the global sensor (unique id format unchanged from 1.x)."""
        super().__init__(coordinator, description)
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.address}_{description.key}"
        self._attr_device_info = scale_device_info(coordinator.address)

    def _snapshot(self) -> PersonState:
        reading = self._coordinator.reading
        return PersonState(
            weight_kg=reading.weight_kg if reading else None,
            impedance_raw=reading.impedance_raw if reading else None,
        )


class AnkoScalePersonSensor(_AnkoRestoreSensor):
    """A measurement attributed to one person, from any scale."""

    def __init__(
        self,
        hub: PeopleHub,
        profile: PersonProfile,
        description: AnkoScaleSensorDescription,
    ) -> None:
        """Initialise a per-person sensor."""
        super().__init__(hub, description)
        self._hub = hub
        self._profile_id = profile.profile_id
        self._attr_unique_id = (
            f"{PERSON_UNIQUE_PREFIX}{profile.profile_id}_{description.key}"
        )
        self._attr_device_info = person_device_info(profile)

    def _snapshot(self) -> PersonState:
        return self._hub.person_states.get(self._profile_id, PersonState())


class AnkoScaleLastPersonSensor(SensorEntity):
    """Name of the person the latest weigh-in was attributed to."""

    _attr_has_entity_name = True
    _attr_translation_key = "last_person"

    def __init__(self, coordinator: AnkoScaleCoordinator) -> None:
        """Initialise the sensor."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.address}_last_person"
        self._attr_device_info = scale_device_info(coordinator.address)

    @property
    def native_value(self) -> str | None:
        """Return the display name of the last attributed person."""
        return self._coordinator.last_person

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )


class AnkoScalePendingCountSensor(SensorEntity):
    """Number of weigh-ins waiting to be assigned to a person."""

    _attr_has_entity_name = True
    _attr_translation_key = "pending_count"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: AnkoScaleCoordinator) -> None:
        """Initialise the sensor."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.address}_pending_count"
        self._attr_device_info = scale_device_info(coordinator.address)

    @property
    def native_value(self) -> int:
        """Return the pending queue length."""
        return len(self._coordinator.pending)

    @property
    def extra_state_attributes(self) -> dict[str, list[dict[str, object]]]:
        """Return the pending measurements (no health data beyond weight)."""
        return {
            "pending": [
                {
                    "pending_id": p.pending_id,
                    "weight_kg": p.weight_kg,
                    "timestamp": p.timestamp.isoformat(),
                    "candidates": p.candidates,
                }
                for p in self._coordinator.pending
            ]
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )
