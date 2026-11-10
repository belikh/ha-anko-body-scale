"""People shared by every scale: profiles, weight history, latest measurements."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from . import body_metrics
from .attribution import PersonProfile, ewma, update_expected_weight
from .const import (
    CONF_ENTRY_TYPE,
    CONF_HISTORY_SIZE,
    CONF_MARGIN_KG,
    CONF_NOTIFY_SERVICE,
    CONF_PENDING_TIMEOUT,
    CONF_PERSONS,
    CONF_TOLERANCE_KG,
    CONF_TOLERANCE_PCT,
    DEFAULT_HISTORY_SIZE,
    DEFAULT_MARGIN_KG,
    DEFAULT_PENDING_TIMEOUT_MIN,
    DEFAULT_TOLERANCE_KG,
    DEFAULT_TOLERANCE_PCT,
    DOMAIN,
    ENTRY_TYPE_PEOPLE,
    EVENT_WEIGH_IN,
    PEOPLE_UNIQUE_ID,
)
from .parser import assumed_ohms
from .store import AnkoScaleStore

if TYPE_CHECKING:
    from .coordinator import AnkoScaleCoordinator

_LOGGER = logging.getLogger(__name__)

HUB_KEY: HassKey[PeopleHub] = HassKey("anko_scale_people_hub")
_HUB_LOCK_KEY: HassKey[asyncio.Lock] = HassKey("anko_scale_people_hub_lock")


def is_people_entry(entry: ConfigEntry) -> bool:
    """Return True for the entry that holds the shared people list."""
    return entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_PEOPLE


def find_people_entry(hass: HomeAssistant) -> ConfigEntry | None:
    """Return the People config entry, if one exists."""
    return hass.config_entries.async_entry_for_domain_unique_id(
        DOMAIN, PEOPLE_UNIQUE_ID
    )


@dataclass
class PersonState:
    """Latest attributed measurement for one person."""

    weight_kg: float | None = None
    impedance_raw: float | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    measured_at: datetime | None = None


@dataclass
class _LastMeasurement:
    """Enough of the previous attribution to undo it on reassignment."""

    scale_entry_id: str
    profile_id: str
    weight_kg: float
    impedance_raw: float | None
    timestamp: datetime
    prev_state: PersonState
    prev_history: list[float]


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class PeopleHub:
    """Holds every person and their latest measurements for all scales.

    A person weighed on any scale updates the same sensors and history.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the hub from the People config entry."""
        self.hass = hass
        self.entry = entry
        options = entry.options
        self.persons: list[PersonProfile] = [
            PersonProfile.from_dict(p) for p in options.get(CONF_PERSONS, [])
        ]
        self.tolerance_kg: float = options.get(CONF_TOLERANCE_KG, DEFAULT_TOLERANCE_KG)
        self.tolerance_pct: float = options.get(
            CONF_TOLERANCE_PCT, DEFAULT_TOLERANCE_PCT
        )
        self.margin_kg: float = options.get(CONF_MARGIN_KG, DEFAULT_MARGIN_KG)
        self.history_size: int = int(
            options.get(CONF_HISTORY_SIZE, DEFAULT_HISTORY_SIZE)
        )
        self.pending_timeout_min: int = int(
            options.get(CONF_PENDING_TIMEOUT, DEFAULT_PENDING_TIMEOUT_MIN)
        )
        self.notify_service: str | None = options.get(CONF_NOTIFY_SERVICE) or None

        self.person_states: dict[str, PersonState] = {
            p.profile_id: PersonState() for p in self.persons
        }
        self.history: dict[str, list[float]] = {p.profile_id: [] for p in self.persons}
        self.last_measured: dict[str, datetime | None] = {
            p.profile_id: None for p in self.persons
        }
        self.last_person_by_scale: dict[str, str] = {}
        self._last_measurement: _LastMeasurement | None = None
        self._scales: dict[str, AnkoScaleCoordinator] = {}
        self._listeners: list[Callable[[], None]] = []
        self._store = AnkoScaleStore(hass, entry.entry_id)

    # ------------------------------------------------------------ lifecycle

    async def async_load(self) -> None:
        """Load persisted history and seed people without any."""
        data = await self._store.async_load()
        stored = data.get("persons", {})
        for person in self.persons:
            saved = stored.get(person.profile_id, {})
            history = [float(v) for v in saved.get("history", [])]
            self.history[person.profile_id] = history[-self.history_size :]
            raw_ts = saved.get("last_measurement")
            if raw_ts:
                try:
                    self.last_measured[person.profile_id] = datetime.fromisoformat(
                        raw_ts
                    )
                except ValueError:
                    _LOGGER.debug("Ignoring bad stored timestamp %s", raw_ts)
            if not self.history[person.profile_id] and person.expected_weight_kg:
                self.history[person.profile_id] = [float(person.expected_weight_kg)]

    async def async_stop(self) -> None:
        """Flush state to disk."""
        await self._store.async_save(self._serialise())

    def register_scale(self, coordinator: AnkoScaleCoordinator) -> Callable[[], None]:
        """Track a scale so people-level actions can reach it."""
        self._scales[coordinator.entry.entry_id] = coordinator

        def _remove() -> None:
            self._scales.pop(coordinator.entry.entry_id, None)

        return _remove

    # ------------------------------------------------------------ listeners

    def async_add_listener(
        self, update_callback: Callable[[], None]
    ) -> Callable[[], None]:
        """Register a callback to be called when person state changes."""
        self._listeners.append(update_callback)

        def _remove() -> None:
            self._listeners.remove(update_callback)

        return _remove

    def notify(self) -> None:
        """Tell person entities and every scale that state changed."""
        for update_listener in list(self._listeners):
            update_listener()
        for scale in list(self._scales.values()):
            scale.notify()

    # --------------------------------------------------------------- lookups

    def profile(self, profile_id: str) -> PersonProfile:
        """Return a person or raise a translated validation error."""
        for person in self.persons:
            if person.profile_id == profile_id:
                return person
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unknown_person",
            translation_placeholders={"person": profile_id},
        )

    def persons_for(self, allowed: list[str] | None) -> list[PersonProfile]:
        """Return the people allowed on a scale; None means everyone."""
        if allowed is None:
            return list(self.persons)
        return [p for p in self.persons if p.profile_id in allowed]

    def expected_weights(self) -> dict[str, float]:
        """Return the EWMA expected weight for every person with history."""
        return {pid: ewma(history) for pid, history in self.history.items() if history}

    def excluded(self) -> set[str]:
        """Return people whose linked HA person entity says they are away."""
        excluded: set[str] = set()
        for person in self.persons:
            if not person.person_entity:
                continue
            state = self.hass.states.get(person.person_entity)
            if state is not None and state.state == "not_home":
                excluded.add(person.profile_id)
        return excluded

    # --------------------------------------------------------------- actions

    def publish(
        self,
        scale_entry_id: str,
        profile_id: str,
        weight_kg: float,
        impedance_raw: float | None,
        timestamp: datetime,
        confidence: float,
        source: str,
    ) -> None:
        """Record a measurement for a person and fire the weigh-in event."""
        profile = self.profile(profile_id)
        metrics = body_metrics.calculate_metrics(
            weight_kg=weight_kg,
            impedance_ohm=assumed_ohms(impedance_raw),
            height_cm=profile.height_cm,
            age=profile.current_age(dt_util.now().date()),
            sex=profile.sex,
        )
        previous_state = self.person_states.get(profile_id, PersonState())
        previous_history = list(self.history.get(profile_id, []))
        self._last_measurement = _LastMeasurement(
            scale_entry_id,
            profile_id,
            weight_kg,
            impedance_raw,
            timestamp,
            previous_state,
            previous_history,
        )
        self.person_states[profile_id] = PersonState(
            weight_kg, impedance_raw, metrics, timestamp
        )
        self.history[profile_id], _ = update_expected_weight(
            previous_history, weight_kg, self.history_size
        )
        self.last_measured[profile_id] = timestamp
        self.last_person_by_scale[scale_entry_id] = profile.display_name
        self._schedule_save()
        self.hass.bus.async_fire(
            EVENT_WEIGH_IN,
            {
                "entry_id": scale_entry_id,
                "person_id": profile_id,
                "person_name": profile.display_name,
                "weight_kg": weight_kg,
                "impedance_raw": impedance_raw,
                "confidence": confidence,
                "source": source,
                "timestamp": timestamp.isoformat(),
            },
        )
        self.notify()

    def reassign_last(self, profile_id: str) -> None:
        """Move the most recent attributed weigh-in to another person."""
        self.profile(profile_id)
        last = self._last_measurement
        if last is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="no_last_measurement"
            )
        if last.profile_id == profile_id:
            return
        self.person_states[last.profile_id] = last.prev_state
        self.history[last.profile_id] = last.prev_history
        self.publish(
            last.scale_entry_id,
            profile_id,
            last.weight_kg,
            last.impedance_raw,
            last.timestamp,
            1.0,
            "reassigned",
        )

    def reset_history(self, profile_id: str) -> None:
        """Forget a person's weight history (re-seeding from their setting)."""
        profile = self.profile(profile_id)
        self.history[profile_id] = (
            [float(profile.expected_weight_kg)] if profile.expected_weight_kg else []
        )
        self._schedule_save()
        self.notify()

    def arm_next(self, profile_id: str) -> None:
        """Assign the next weigh-in on any scale that allows this person."""
        self.profile(profile_id)
        armed = False
        for scale in self._scales.values():
            if any(p.profile_id == profile_id for p in scale.persons):
                scale.async_set_next_person(profile_id)
                armed = True
        if not armed:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="no_scale_for_person"
            )

    # ----------------------------------------------------------- persistence

    def _serialise(self) -> dict[str, Any]:
        return {
            "persons": {
                pid: {
                    "history": self.history.get(pid, []),
                    "last_measurement": _iso(self.last_measured.get(pid)),
                    "last_impedance_raw": self.person_states[pid].impedance_raw,
                }
                for pid in self.person_states
            }
        }

    def _schedule_save(self) -> None:
        self._store.async_schedule_save(self._serialise)


async def async_ensure_hub(hass: HomeAssistant, entry: ConfigEntry) -> PeopleHub:
    """Return the shared hub, creating it once whichever entry asks first.

    Home Assistant sets entries up concurrently, so a scale can start before
    the People entry. The lock makes both paths share one hub.
    """
    lock = hass.data.setdefault(_HUB_LOCK_KEY, asyncio.Lock())
    async with lock:
        hub = hass.data.get(HUB_KEY)
        if hub is None:
            hub = PeopleHub(hass, entry)
            await hub.async_load()
            hass.data[HUB_KEY] = hub
        return hub


async def async_release_hub(hass: HomeAssistant) -> None:
    """Flush and drop the shared hub."""
    lock = hass.data.setdefault(_HUB_LOCK_KEY, asyncio.Lock())
    async with lock:
        hub = hass.data.pop(HUB_KEY, None)
        if hub is not None:
            await hub.async_stop()
