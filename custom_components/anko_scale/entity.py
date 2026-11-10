"""Shared device-registry helpers."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo

from .attribution import PersonProfile
from .const import DOMAIN, PERSON_DEVICE_PREFIX


def scale_device_info(address: str) -> DeviceInfo:
    """Return the DeviceInfo of a scale (registered in async_setup_entry)."""
    return DeviceInfo(identifiers={(DOMAIN, address)})


def person_device_info(profile: PersonProfile) -> DeviceInfo:
    """Return the DeviceInfo of one person (registered by the People entry)."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{PERSON_DEVICE_PREFIX}{profile.profile_id}")}
    )
