"""The ANKO Body Scale integration."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback

from . import body_metrics
from .const import CONF_AGE, CONF_HEIGHT_CM, CONF_SEX, DOMAIN
from .parser import ScaleReading, parse_manufacturer_data

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


class AnkoScaleCoordinator:
    """Receives passive BLE adverts from the scale and computes body metrics."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the coordinator for one config entry."""
        self.hass = hass
        self.entry = entry
        self.address: str = entry.data["address"]
        self.reading: ScaleReading | None = None
        self.metrics: dict[str, float] = {}
        self._listeners: list[Callable[[], None]] = []
        self._unregister_callback: Callable[[], None] | None = None

    @property
    def profile(self) -> dict:
        """Return the configured height/age/sex profile."""
        options = self.entry.options
        return {
            CONF_HEIGHT_CM: options[CONF_HEIGHT_CM],
            CONF_AGE: options[CONF_AGE],
            CONF_SEX: options[CONF_SEX],
        }

    @callback
    def _async_handle_advertisement(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        reading = parse_manufacturer_data(service_info.manufacturer_data)
        if reading is None:
            return

        self.reading = reading

        if reading.stable and reading.impedance_ohm:
            profile = self.profile
            self.metrics = body_metrics.calculate_metrics(
                weight_kg=reading.weight_kg,
                impedance_ohm=reading.impedance_ohm,
                height_cm=profile[CONF_HEIGHT_CM],
                age=profile[CONF_AGE],
                sex=profile[CONF_SEX],
            )

        for update_listener in self._listeners:
            update_listener()

    def async_add_listener(
        self, update_callback: Callable[[], None]
    ) -> Callable[[], None]:
        """Register a callback to be called when a new reading arrives."""
        self._listeners.append(update_callback)

        def _remove() -> None:
            self._listeners.remove(update_callback)

        return _remove

    def async_start(self) -> None:
        """Start listening for passive BLE adverts from the scale."""
        self._unregister_callback = bluetooth.async_register_callback(
            self.hass,
            self._async_handle_advertisement,
            bluetooth.BluetoothCallbackMatcher(address=self.address),
            bluetooth.BluetoothScanningMode.PASSIVE,
        )

    def async_stop(self) -> None:
        """Stop listening for adverts."""
        if self._unregister_callback:
            self._unregister_callback()
            self._unregister_callback = None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the ANKO Body Scale from a config entry."""
    coordinator = AnkoScaleCoordinator(hass, entry)
    coordinator.async_start()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    entry.async_on_unload(coordinator.async_stop)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options (the body profile) change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
