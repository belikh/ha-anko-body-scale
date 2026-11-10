"""Tests for translation metadata completeness."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

COMPONENT_DIR = (
    Path(__file__).resolve().parent.parent / "custom_components" / "anko_scale"
)

ENTITY_KEYS: dict[str, set[str]] = {
    "sensor": {
        "weight",
        "impedance",
        "bmi",
        "body_fat_percent",
        "fat_mass",
        "lean_mass",
        "muscle_mass",
        "body_water",
        "bone_mass",
        "bmr",
        "metabolic_age",
        "visceral_fat_index",
        "ideal_weight_min",
        "ideal_weight_max",
        "last_person",
        "pending_count",
    },
    "binary_sensor": {"reading_stable"},
    "button": {"weighing_in"},
    "select": {"next_person"},
}

FLOW_STEPS = {
    "config": {"user", "profile", "people", "bluetooth_confirm"},
    "options": {
        "init",
        "add_person",
        "add_from_person",
        "scale_people",
        "edit_person",
        "edit_person_form",
        "delete_person",
        "settings",
    },
}
SERVICES = {
    "assign_measurement",
    "discard_measurement",
    "capture_measurement",
    "reassign_measurement",
    "set_next_person",
    "reset_person_history",
}
EXCEPTIONS = {
    "unknown_person",
    "unknown_pending",
    "no_last_measurement",
    "unknown_entry",
    "entry_required",
    "capture_timeout",
    "capture_in_progress",
    "people_unavailable",
    "no_scale_for_person",
    "people_missing",
    "people_adopting",
}


def _load_json(relative: str) -> dict[str, Any]:
    return json.loads((COMPONENT_DIR / relative).read_text(encoding="utf-8"))


def test_entity_keys_complete_with_names() -> None:
    translations = _load_json("translations/en.json")
    entity = translations["entity"]
    for platform, keys in ENTITY_KEYS.items():
        for key in keys:
            assert entity[platform][key]["name"], f"{platform}.{key} missing name"


def test_translations_match_strings() -> None:
    assert _load_json("translations/en.json") == _load_json("strings.json")


def test_flow_steps_and_errors_present() -> None:
    translations = _load_json("translations/en.json")
    for section, steps in FLOW_STEPS.items():
        assert steps <= set(translations[section]["step"]), section
    assert {
        "name_required",
        "name_exists",
        "invalid_birth_date",
        "birth_date_or_age",
    } <= set(translations["config"]["error"])
    assert {
        "name_required",
        "name_exists",
        "invalid_birth_date",
        "birth_date_or_age",
    } <= set(translations["options"]["error"])
    assert "people_required" in translations["config"]["error"]
    assert "people_required" in translations["options"]["error"]
    assert {"no_devices_found", "already_configured"} <= set(
        translations["config"]["abort"]
    )


def test_services_and_exceptions_translated() -> None:
    translations = _load_json("translations/en.json")
    assert set(translations["services"]) == SERVICES
    assert set(translations["exceptions"]) >= EXCEPTIONS
    services_yaml = (COMPONENT_DIR / "services.yaml").read_text(encoding="utf-8")
    for service in SERVICES:
        assert f"\n{service}:" in f"\n{services_yaml}"
