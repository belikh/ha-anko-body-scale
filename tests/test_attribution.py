"""Tests for the pure attribution logic."""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "anko_scale"
    / "attribution.py"
)
_spec = importlib.util.spec_from_file_location("anko_attribution", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
sys.modules["anko_attribution"] = _module
_spec.loader.exec_module(_module)

PersonProfile = _module.PersonProfile
age_from_birth_date = _module.age_from_birth_date
is_valid_profile_id = _module.is_valid_profile_id
score = _module.score
tolerance_for = _module.tolerance_for
update_expected_weight = _module.update_expected_weight

A = PersonProfile("alice", "Alice", 165, "female")
B = PersonProfile("bob", "Bob", 180, "male")
EXPECTED = {"alice": 60.0, "bob": 85.0}


def test_single_clear_match() -> None:
    result = score(61.2, [A, B], EXPECTED)
    assert result.profile_id == "alice"
    assert result.reason == "weight_match"
    assert result.candidates[0].within_tolerance


def test_overlap_is_pending() -> None:
    expected = {"alice": 70.0, "bob": 71.0}
    result = score(70.4, [A, B], expected)
    assert result.profile_id is None
    assert result.reason == "ambiguous"
    assert len(result.candidates) == 2


def test_no_match_is_pending() -> None:
    result = score(120.0, [A, B], EXPECTED)
    assert result.profile_id is None
    assert result.reason == "no_match"


def test_single_person_bypass() -> None:
    assert score(200.0, [A], {}).profile_id == "alice"


def test_single_person_excluded_is_pending() -> None:
    result = score(60.0, [A], {}, excluded={"alice"})
    assert result.profile_id is None


def test_excluded_person_never_assigned() -> None:
    result = score(61.0, [A, B], EXPECTED, excluded={"alice"})
    assert result.profile_id is None
    assert result.reason == "no_match"


def test_force_wins_over_scoring() -> None:
    result = score(61.0, [A, B], EXPECTED, force_profile_id="bob")
    assert result.profile_id == "bob"
    assert result.reason == "forced"


def test_unknown_force_id_ignored() -> None:
    result = score(61.0, [A, B], EXPECTED, force_profile_id="nobody")
    assert result.profile_id == "alice"


def test_unseeded_people_are_pending() -> None:
    result = score(61.0, [A, B], {})
    assert result.profile_id is None


def test_tolerance_is_max_of_fixed_and_percent() -> None:
    assert tolerance_for(50.0) == 5.0
    assert tolerance_for(100.0) == 7.0


def test_ewma_and_history_cap() -> None:
    history, ewma = update_expected_weight([], 70.0)
    assert (history, ewma) == ([70.0], 70.0)
    history, ewma = update_expected_weight(history, 80.0)
    assert round(ewma, 2) == 73.0
    long_history = [70.0] * 60
    capped, _ = update_expected_weight(long_history, 71.0, history_size=50)
    assert len(capped) == 50


def test_age_from_birth_date() -> None:
    assert age_from_birth_date(date(1990, 6, 15), date(2026, 6, 14)) == 35
    assert age_from_birth_date(date(1990, 6, 15), date(2026, 6, 15)) == 36


def test_profile_from_dict_and_age() -> None:
    profile = PersonProfile.from_dict(
        {
            "profile_id": "x",
            "display_name": "X",
            "height_cm": 170,
            "sex": "male",
            "birth_date": "1990-01-01",
        }
    )
    assert profile.current_age(date(2026, 1, 1)) == 36
    legacy = PersonProfile.from_dict(
        {
            "profile_id": "l",
            "display_name": "L",
            "height_cm": 170,
            "sex": "male",
            "age": 41,
        }
    )
    assert legacy.current_age(date(2026, 1, 1)) == 41


def test_profile_id_slug() -> None:
    assert is_valid_profile_id("jupiter_2")
    assert not is_valid_profile_id("Jupiter 2")
    assert not is_valid_profile_id("")
