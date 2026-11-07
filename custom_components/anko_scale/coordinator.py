"""Coordinator: BLE adverts -> settled weigh-ins -> attributed measurements."""

from __future__ import annotations

import asyncio
import logging
import secrets
import statistics
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components import bluetooth, persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.util import dt as dt_util

from . import body_metrics
from .attribution import (
    Attribution,
    PersonProfile,
    confidence_for,
    ewma,
    score,
    update_expected_weight,
)
from .const import (
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
    EVENT_PENDING,
    EVENT_WEIGH_IN,
    FORCE_ASSIGN_TIMEOUT_S,
    SETTLE_FRAMES,
    SETTLE_SPREAD_KG,
    SETTLE_TIMEOUT_S,
    SETTLE_WINDOW_S,
)
from .parser import ScaleReading, parse_manufacturer_data
from .store import AnkoScaleStore

_LOGGER = logging.getLogger(__name__)

MAX_PENDING = 10
MAX_RECENT_FRAMES = 30
MOBILE_ACTION_EVENT = "mobile_app_notification_action"
ACTION_ASSIGN_PREFIX = "ANKO_ASSIGN"
ACTION_DISCARD_PREFIX = "ANKO_DISCARD"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


@dataclass
class PersonState:
    """Latest attributed measurement for one person."""

    weight_kg: float | None = None
    impedance_ohm: float | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    measured_at: datetime | None = None


@dataclass
class PendingMeasurement:
    """A settled weigh-in waiting for a person to be chosen."""

    pending_id: str
    weight_kg: float
    impedance_ohm: float
    timestamp: datetime
    candidates: list[dict[str, Any]]
    reason: str = "ambiguous"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable form."""
        return {
            "pending_id": self.pending_id,
            "weight_kg": self.weight_kg,
            "impedance_ohm": self.impedance_ohm,
            "timestamp": self.timestamp.isoformat(),
            "candidates": self.candidates,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PendingMeasurement:
        """Rebuild from the stored form."""
        return cls(
            pending_id=data["pending_id"],
            weight_kg=float(data["weight_kg"]),
            impedance_ohm=float(data["impedance_ohm"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            candidates=list(data.get("candidates", [])),
            reason=str(data.get("reason", "ambiguous")),
        )


@dataclass
class _Frame:
    at: float
    weight_kg: float
    impedance_ohm: float


@dataclass
class _LastMeasurement:
    """Enough of the previous attribution to undo it on reassignment."""

    profile_id: str
    weight_kg: float
    impedance_ohm: float
    timestamp: datetime
    prev_state: PersonState
    prev_history: list[float]


class AnkoScaleCoordinator:
    """Receives passive BLE adverts and publishes attributed weigh-ins."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the coordinator for one config entry."""
        self.hass = hass
        self.entry = entry
        self.address: str = entry.data["address"]
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
        self.pending_timeout = timedelta(
            minutes=options.get(CONF_PENDING_TIMEOUT, DEFAULT_PENDING_TIMEOUT_MIN)
        )
        self.notify_service: str | None = options.get(CONF_NOTIFY_SERVICE) or None

        self.reading: ScaleReading | None = None
        self.metrics: dict[str, float] = {}
        self.last_person: str | None = None
        self.person_states: dict[str, PersonState] = {
            p.profile_id: PersonState() for p in self.persons
        }
        self.pending: list[PendingMeasurement] = []
        self.history: dict[str, list[float]] = {p.profile_id: [] for p in self.persons}
        self.last_measured: dict[str, datetime | None] = {
            p.profile_id: None for p in self.persons
        }
        self._last_measurement: _LastMeasurement | None = None

        self._force_profile_id: str | None = None
        self._force_expires: float = 0.0
        self._force_cancel: CALLBACK_TYPE | None = None

        # Diagnostics
        self.rssi: int | None = None
        self.last_raw_hex: str | None = None
        self.recent_frames: deque[dict[str, Any]] = deque(maxlen=MAX_RECENT_FRAMES)
        self.frame_count = 0
        self.stable_frame_count = 0
        self.weigh_in_count = 0
        self.unknown_weight_count = 0
        self._capture: asyncio.Future[dict[str, Any]] | None = None

        self._buffer: list[_Frame] = []
        self._finalised = False
        self._settle_cancel: CALLBACK_TYPE | None = None
        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._store = AnkoScaleStore(hass, entry.entry_id)

    # ------------------------------------------------------------------ setup

    async def async_load(self) -> None:
        """Load persisted history and pending queue, then seed new people."""
        data = await self._store.async_load()
        stored_persons = data.get("persons", {})
        for person in self.persons:
            saved = stored_persons.get(person.profile_id, {})
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

        for raw in data.get("pending", []):
            try:
                self.pending.append(PendingMeasurement.from_dict(raw))
            except KeyError, ValueError, TypeError:
                _LOGGER.debug("Dropping unreadable pending measurement")
        self._expire_pending()
        for pending in self.pending:
            if pending.reason == "no_match":
                self._create_unknown_issue(pending)

    @callback
    def async_start(self) -> None:
        """Start listening for adverts, notification actions and expiry."""
        self._unsubs.append(
            bluetooth.async_register_callback(
                self.hass,
                self._async_handle_advertisement,
                bluetooth.BluetoothCallbackMatcher(address=self.address),
                bluetooth.BluetoothScanningMode.PASSIVE,
            )
        )
        self._unsubs.append(
            self.hass.bus.async_listen(MOBILE_ACTION_EVENT, self._async_mobile_action)
        )
        self._unsubs.append(
            async_track_time_interval(
                self.hass, self._async_expire_tick, timedelta(minutes=5)
            )
        )

    async def async_stop(self) -> None:
        """Stop listening and flush state to disk."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._cancel_settle_timer()
        self._cancel_force_timer()
        if self._capture is not None and not self._capture.done():
            self._capture.cancel()
        await self._store.async_save(self._serialise())

    # -------------------------------------------------------------- listeners

    def async_add_listener(
        self, update_callback: Callable[[], None]
    ) -> Callable[[], None]:
        """Register a callback to be called when state changes."""
        self._listeners.append(update_callback)

        def _remove() -> None:
            self._listeners.remove(update_callback)

        return _remove

    def _notify(self) -> None:
        for update_listener in list(self._listeners):
            update_listener()

    # ----------------------------------------------------------- BLE ingestion

    @callback
    def _async_handle_advertisement(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        reading = parse_manufacturer_data(service_info.manufacturer_data)
        if reading is None:
            return
        self.rssi = service_info.rssi
        self.last_raw_hex = " ".join(
            f"{key:04x}:{value.hex()}"
            for key, value in service_info.manufacturer_data.items()
        )
        if not self.recent_frames or self.recent_frames[-1]["hex"] != self.last_raw_hex:
            self.recent_frames.append(
                {
                    "time": dt_util.utcnow().isoformat(timespec="seconds"),
                    "hex": self.last_raw_hex,
                    "weight_kg": reading.weight_kg,
                    "impedance_ohm": reading.impedance_ohm,
                    "stable": reading.stable,
                    "rssi": service_info.rssi,
                }
            )
        self.async_handle_reading(reading, time.monotonic())

    @callback
    def async_handle_reading(self, reading: ScaleReading, now: float) -> None:
        """Process one decoded advert at monotonic time `now`."""
        self.reading = reading
        self.frame_count += 1
        self._cancel_settle_timer()

        if reading.stable and reading.impedance_ohm:
            self.stable_frame_count += 1
            self._add_stable_frame(
                _Frame(now, reading.weight_kg, reading.impedance_ohm)
            )
        else:
            self._buffer.clear()
            self._finalised = False

        self._notify()

        if self._buffer:
            self._settle_cancel = async_call_later(
                self.hass, SETTLE_TIMEOUT_S, self._async_settle_timeout
            )

    def _cancel_settle_timer(self) -> None:
        if self._settle_cancel:
            self._settle_cancel()
            self._settle_cancel = None

    def _add_stable_frame(self, frame: _Frame) -> None:
        if self._buffer and frame.at - self._buffer[-1].at > SETTLE_TIMEOUT_S:
            # The scale went quiet between weigh-ins.
            self._buffer = []
            self._finalised = False
        window = [f for f in self._buffer if frame.at - f.at <= SETTLE_WINDOW_S]
        weights = [f.weight_kg for f in window] + [frame.weight_kg]
        if max(weights) - min(weights) > SETTLE_SPREAD_KG:
            # Weight moved: treat as a new weigh-in.
            window = []
            self._finalised = False
        window.append(frame)
        self._buffer = window
        if (
            not self._finalised
            and len(window) >= SETTLE_FRAMES
            and window[-1].at - window[-SETTLE_FRAMES].at <= SETTLE_WINDOW_S
        ):
            self._finalise_buffer()

    @callback
    def _async_settle_timeout(self, _now: datetime) -> None:
        """No advert for SETTLE_TIMEOUT_S: finalise the last frames, then reset."""
        self._settle_cancel = None
        if self._buffer and not self._finalised:
            self._finalise_buffer()
        self._buffer = []
        self._finalised = False

    def _finalise_buffer(self) -> None:
        frames = self._buffer[-SETTLE_FRAMES:]
        weight = round(statistics.fmean(f.weight_kg for f in frames), 2)
        impedance = round(statistics.fmean(f.impedance_ohm for f in frames), 1)
        self._finalised = True
        self._handle_weigh_in(weight, impedance, dt_util.utcnow())

    # ------------------------------------------------------------ attribution

    def expected_weights(self) -> dict[str, float]:
        """Return the EWMA expected weight for every person with history."""
        return {pid: ewma(history) for pid, history in self.history.items() if history}

    def _excluded(self) -> set[str]:
        excluded: set[str] = set()
        for person in self.persons:
            if not person.person_entity:
                continue
            state = self.hass.states.get(person.person_entity)
            if state is not None and state.state == "not_home":
                excluded.add(person.profile_id)
        return excluded

    def _active_force(self) -> str | None:
        if self._force_profile_id and time.monotonic() <= self._force_expires:
            return self._force_profile_id
        self._force_profile_id = None
        return None

    @property
    def next_person(self) -> str | None:
        """Return the profile_id armed for the next weigh-in, if any."""
        return self._active_force()

    def _handle_weigh_in(
        self, weight_kg: float, impedance_ohm: float, timestamp: datetime
    ) -> None:
        if self._capture is not None and not self._capture.done():
            self._capture.set_result(
                {"weight_kg": weight_kg, "timestamp": timestamp.isoformat()}
            )
            return
        self._expire_pending()
        self.weigh_in_count += 1
        force = self._active_force()
        result = score(
            weight_kg,
            self.persons,
            self.expected_weights(),
            excluded=self._excluded(),
            force_profile_id=force,
            tolerance_kg=self.tolerance_kg,
            tolerance_pct=self.tolerance_pct,
            margin_kg=self.margin_kg,
        )
        if force is not None:
            self._force_profile_id = None

        if result.profile_id is not None:
            self._publish(
                result.profile_id,
                weight_kg,
                impedance_ohm,
                timestamp,
                confidence_for(result, self.margin_kg),
                result.reason,
            )
        else:
            self._add_pending(weight_kg, impedance_ohm, timestamp, result)
        self._notify()

    def _profile(self, profile_id: str) -> PersonProfile:
        for person in self.persons:
            if person.profile_id == profile_id:
                return person
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unknown_person",
            translation_placeholders={"person": profile_id},
        )

    def _publish(
        self,
        profile_id: str,
        weight_kg: float,
        impedance_ohm: float,
        timestamp: datetime,
        confidence: float,
        source: str,
    ) -> None:
        profile = self._profile(profile_id)
        metrics = body_metrics.calculate_metrics(
            weight_kg=weight_kg,
            impedance_ohm=impedance_ohm,
            height_cm=profile.height_cm,
            age=profile.current_age(dt_util.now().date()),
            sex=profile.sex,
        )
        previous_state = self.person_states.get(profile_id, PersonState())
        previous_history = list(self.history.get(profile_id, []))
        self._last_measurement = _LastMeasurement(
            profile_id,
            weight_kg,
            impedance_ohm,
            timestamp,
            previous_state,
            previous_history,
        )
        self.person_states[profile_id] = PersonState(
            weight_kg, impedance_ohm, metrics, timestamp
        )
        self.history[profile_id], _ = update_expected_weight(
            previous_history, weight_kg, self.history_size
        )
        self.last_measured[profile_id] = timestamp
        self.metrics = metrics
        self.last_person = profile.display_name
        self._schedule_save()
        self.hass.bus.async_fire(
            EVENT_WEIGH_IN,
            {
                "entry_id": self.entry.entry_id,
                "person_id": profile_id,
                "person_name": profile.display_name,
                "weight_kg": weight_kg,
                "impedance_ohm": impedance_ohm,
                "confidence": confidence,
                "source": source,
                "timestamp": timestamp.isoformat(),
            },
        )

    # ---------------------------------------------------------------- pending

    def _add_pending(
        self,
        weight_kg: float,
        impedance_ohm: float,
        timestamp: datetime,
        result: Attribution,
    ) -> None:
        candidates = [
            {"person_id": c.profile_id, "distance_kg": round(c.distance_kg, 2)}
            for c in result.candidates
        ]
        pending = PendingMeasurement(
            secrets.token_hex(4),
            weight_kg,
            impedance_ohm,
            timestamp,
            candidates,
            result.reason,
        )
        self.pending.append(pending)
        del self.pending[:-MAX_PENDING]
        self._schedule_save()
        self.hass.bus.async_fire(
            EVENT_PENDING,
            {
                "entry_id": self.entry.entry_id,
                "pending_id": pending.pending_id,
                "weight_kg": weight_kg,
                "impedance_ohm": impedance_ohm,
                "candidates": candidates,
                "reason": result.reason,
                "timestamp": timestamp.isoformat(),
            },
        )
        self._send_notifications(pending)
        if pending.reason == "no_match":
            self.unknown_weight_count += 1
            _LOGGER.info(
                "Weigh-in of %.1f kg matches nobody; offering to add a person",
                weight_kg,
            )
            self._create_unknown_issue(pending)

    def _create_unknown_issue(self, pending: PendingMeasurement) -> None:
        """Offer to add a person for a weight that matches nobody."""
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            f"unknown_weight_{pending.pending_id}",
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="unknown_weight",
            translation_placeholders={"weight": f"{pending.weight_kg:.1f}"},
            data={
                "entry_id": self.entry.entry_id,
                "pending_id": pending.pending_id,
                "weight_kg": pending.weight_kg,
            },
        )

    def _send_notifications(self, pending: PendingMeasurement) -> None:
        names = {p.profile_id: p.display_name for p in self.persons}
        ordered = [c["person_id"] for c in pending.candidates] or list(names)
        message = (
            f"A {pending.weight_kg:.1f} kg weigh-in could not be matched to one "
            "person. Use the anko_scale.assign_measurement action with "
            f"pending_id {pending.pending_id}."
        )
        persistent_notification.async_create(
            self.hass,
            message,
            title="ANKO scale: who was that?",
            notification_id=f"{DOMAIN}_{pending.pending_id}",
        )
        if not self.notify_service or "." not in self.notify_service:
            return
        domain, service = self.notify_service.split(".", 1)
        actions = [
            {
                "action": f"{ACTION_ASSIGN_PREFIX}|{pending.pending_id}|{pid}",
                "title": f"I'm {names[pid]}",
            }
            for pid in ordered[:2]
            if pid in names
        ]
        actions.append(
            {
                "action": f"{ACTION_DISCARD_PREFIX}|{pending.pending_id}",
                "title": "Not me",
            }
        )
        self.hass.async_create_task(
            self.hass.services.async_call(
                domain,
                service,
                {
                    "title": "Who just weighed in?",
                    "message": f"{pending.weight_kg:.1f} kg",
                    "data": {"actions": actions, "tag": pending.pending_id},
                },
            )
        )

    @callback
    def _async_mobile_action(self, event: Event) -> None:
        action = str(event.data.get("action", ""))
        parts = action.split("|")
        try:
            if parts[0] == ACTION_ASSIGN_PREFIX and len(parts) == 3:
                self.async_assign_pending(parts[1], parts[2])
            elif parts[0] == ACTION_DISCARD_PREFIX and len(parts) == 2:
                self.async_discard_pending(parts[1])
        except ServiceValidationError:
            _LOGGER.debug("Notification action %s no longer applies", action)

    def _expire_pending(self) -> None:
        cutoff = dt_util.utcnow() - self.pending_timeout
        expired = [p for p in self.pending if p.timestamp < cutoff]
        for pending in expired:
            self._drop_pending(pending)

    @callback
    def _async_expire_tick(self, _now: datetime) -> None:
        before = len(self.pending)
        self._expire_pending()
        if len(self.pending) != before:
            self._notify()

    def _drop_pending(self, pending: PendingMeasurement) -> None:
        self.pending.remove(pending)
        persistent_notification.async_dismiss(
            self.hass, f"{DOMAIN}_{pending.pending_id}"
        )
        ir.async_delete_issue(self.hass, DOMAIN, f"unknown_weight_{pending.pending_id}")
        self._schedule_save()

    def _find_pending(self, pending_id: str) -> PendingMeasurement:
        for pending in self.pending:
            if pending.pending_id == pending_id:
                return pending
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unknown_pending",
            translation_placeholders={"pending_id": pending_id},
        )

    # ---------------------------------------------------------- public actions

    async def async_capture_measurement(self, wait_s: int) -> dict[str, Any]:
        """Return the next settled weigh-in without assigning it to anyone."""
        if self._capture is not None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="capture_in_progress"
            )
        self._capture = self.hass.loop.create_future()
        try:
            async with asyncio.timeout(wait_s):
                return await self._capture
        except TimeoutError:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="capture_timeout"
            ) from None
        finally:
            self._capture = None

    @callback
    def async_assign_pending(self, pending_id: str, profile_id: str) -> None:
        """Assign a pending weigh-in to a person and publish their metrics."""
        self._profile(profile_id)
        pending = self._find_pending(pending_id)
        self._drop_pending(pending)
        self._publish(
            profile_id,
            pending.weight_kg,
            pending.impedance_ohm,
            pending.timestamp,
            1.0,
            "assigned",
        )
        self._notify()

    @callback
    def async_discard_pending(self, pending_id: str) -> None:
        """Discard a pending weigh-in (a guest). No profile is created."""
        self._drop_pending(self._find_pending(pending_id))
        self._notify()

    @callback
    def async_reassign_last(self, profile_id: str) -> None:
        """Move the most recent attributed weigh-in to another person."""
        self._profile(profile_id)
        last = self._last_measurement
        if last is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="no_last_measurement"
            )
        if last.profile_id == profile_id:
            return
        self.person_states[last.profile_id] = last.prev_state
        self.history[last.profile_id] = last.prev_history
        self._publish(
            profile_id,
            last.weight_kg,
            last.impedance_ohm,
            last.timestamp,
            1.0,
            "reassigned",
        )
        self._notify()

    @callback
    def async_set_next_person(self, profile_id: str | None) -> None:
        """Arm (or clear) a one-shot assignment for the next weigh-in."""
        if profile_id is None:
            self._force_profile_id = None
            self._cancel_force_timer()
        else:
            self._profile(profile_id)
            self._force_profile_id = profile_id
            self._force_expires = time.monotonic() + FORCE_ASSIGN_TIMEOUT_S
            self._cancel_force_timer()
            self._force_cancel = async_call_later(
                self.hass, FORCE_ASSIGN_TIMEOUT_S + 0.5, self._async_force_expired
            )
        self._notify()

    def _cancel_force_timer(self) -> None:
        if self._force_cancel:
            self._force_cancel()
            self._force_cancel = None

    @callback
    def _async_force_expired(self, _now: datetime) -> None:
        self._force_cancel = None
        if self._force_profile_id and time.monotonic() > self._force_expires:
            self._force_profile_id = None
            self._notify()

    @callback
    def async_reset_person_history(self, profile_id: str) -> None:
        """Forget a person's weight history (re-seeding from their setting)."""
        profile = self._profile(profile_id)
        self.history[profile_id] = (
            [float(profile.expected_weight_kg)] if profile.expected_weight_kg else []
        )
        self._schedule_save()
        self._notify()

    # ------------------------------------------------------------ persistence

    def _serialise(self) -> dict[str, Any]:
        return {
            "persons": {
                pid: {
                    "history": self.history.get(pid, []),
                    "last_measurement": _iso(self.last_measured.get(pid)),
                    "last_impedance": self.person_states[pid].impedance_ohm,
                }
                for pid in self.person_states
            },
            "pending": [p.to_dict() for p in self.pending],
        }

    def _schedule_save(self) -> None:
        self._store.async_schedule_save(self._serialise)
