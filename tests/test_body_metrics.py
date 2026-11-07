"""Tests for the body-composition calculations."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "anko_scale"
    / "body_metrics.py"
)
_spec = importlib.util.spec_from_file_location("anko_body_metrics", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
sys.modules["anko_body_metrics"] = _module
_spec.loader.exec_module(_module)

calculate_metrics = _module.calculate_metrics


def test_calculate_metrics_keys_and_sanity() -> None:
    metrics = calculate_metrics(
        weight_kg=70.0,
        impedance_ohm=500.0,
        height_cm=175,
        age=30,
        sex="male",
    )
    assert set(metrics) == {
        "bmi",
        "body_fat_percent",
        "fat_mass_kg",
        "lean_mass_kg",
        "muscle_mass_kg",
        "body_water_percent",
        "bone_mass_kg",
        "bmr",
        "metabolic_age",
        "visceral_fat_index",
        "ideal_weight_min_kg",
        "ideal_weight_max_kg",
    }
    assert metrics["bmi"] == round(70.0 / 1.75**2, 1)
    fat_mass = metrics["fat_mass_kg"]
    lean_mass = metrics["lean_mass_kg"]
    assert fat_mass + lean_mass == 70.0
    assert 5.0 < metrics["body_fat_percent"] < 50.0
    assert 1 <= metrics["visceral_fat_index"] <= 30
    assert metrics["ideal_weight_min_kg"] < metrics["ideal_weight_max_kg"]


def test_calculate_metrics_female_bmr_differs() -> None:
    male = calculate_metrics(65.0, 550.0, 165, 35, "male")
    female = calculate_metrics(65.0, 550.0, 165, 35, "female")
    assert female["bmr"] < male["bmr"]
