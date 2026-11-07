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
    },
    "binary_sensor": {"reading_stable"},
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
