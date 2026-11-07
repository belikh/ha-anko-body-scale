"""Shared device-registry helpers."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo

from .attribution import PersonProfile
from .const import DOMAIN


def scale_device_info(address: str) -> DeviceInfo:
    """Return the DeviceInfo of the scale (registered in async_setup_entry)."""
    return DeviceInfo(identifiers={(DOMAIN, address)})


def person_device_info(address: str, profile: PersonProfile) -> DeviceInfo:
    """Return the DeviceInfo of one person (registered in async_setup_entry)."""
    return DeviceInfo(identifiers={(DOMAIN, f"{address}:{profile.profile_id}")})
