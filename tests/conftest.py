"""Shared fixtures for integration-level tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

import pytest

ADDRESS = "AA:BB:CC:DD:EE:FF"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load custom_components from the working tree."""


@pytest.fixture
def mock_bluetooth(hass) -> Generator[None]:
    """Pretend the bluetooth dependency is loaded and capture the callback."""
    hass.config.components.add("bluetooth")
    with patch(
        "custom_components.anko_scale.coordinator.bluetooth.async_register_callback",
        return_value=lambda: None,
    ):
        yield
