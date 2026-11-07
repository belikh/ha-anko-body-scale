"""Tests for the body-composition calculations."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

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
        "bia_valid",
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


def test_wu_equation_matches_hand_calculation() -> None:
    metrics = calculate_metrics(70.0, 500.0, 175, 30, "male")
    ffm = 13.055 + 0.204 * 70 + 0.394 * 175**2 / 500 - 0.136 * 30 + 8.125
    assert metrics["bia_valid"] == 1.0
    assert metrics["lean_mass_kg"] == round(ffm, 2)
    assert metrics["body_fat_percent"] == round((70 - ffm) / 70 * 100, 1)


def test_implausible_ffm_falls_back_to_bmi() -> None:
    # Live reading: 329 ohm gives an FFM above body weight in the Wu equation.
    metrics = calculate_metrics(61.55, 329.3, 183, 30, "male")
    bmi = 61.55 / 1.83**2
    expected = 1.20 * bmi + 0.23 * 30 - 10.8 - 5.4
    assert metrics["bia_valid"] == 0.0
    assert metrics["body_fat_percent"] == round(expected, 1)
    assert metrics["fat_mass_kg"] + metrics["lean_mass_kg"] == pytest.approx(
        61.55, abs=0.01
    )


def test_impedance_outside_validated_range_falls_back() -> None:
    low = calculate_metrics(70.0, 200.0, 175, 30, "male")
    high = calculate_metrics(70.0, 900.0, 175, 30, "male")
    assert low["bia_valid"] == 0.0
    assert high["bia_valid"] == 0.0


def test_child_uses_child_bmi_formula() -> None:
    metrics = calculate_metrics(40.0, 600.0, 150, 12, "female")
    bmi = 40.0 / 1.5**2
    expected = 1.51 * bmi - 0.70 * 12 + 1.4
    assert metrics["bia_valid"] == 0.0
    assert metrics["body_fat_percent"] == round(expected, 1)


def test_missing_impedance_uses_bmi_route() -> None:
    metrics = calculate_metrics(70.0, None, 175, 30, "male")
    assert metrics["bia_valid"] == 0.0
