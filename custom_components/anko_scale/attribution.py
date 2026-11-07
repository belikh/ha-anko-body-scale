"""Pure weight-based attribution of a reading to a person (no HA imports)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

EWMA_ALPHA = 0.3
DEFAULT_HISTORY_SIZE = 50
DEFAULT_TOLERANCE_KG = 5.0
DEFAULT_TOLERANCE_PCT = 7.0
DEFAULT_MARGIN_KG = 2.0

_SLUG_RE = re.compile(r"^[a-z0-9_]+$")


def is_valid_profile_id(profile_id: str) -> bool:
    """Return True if the id is a lowercase slug usable in unique ids."""
    return bool(_SLUG_RE.match(profile_id))


def age_from_birth_date(birth_date: date, today: date) -> int:
    """Return whole years between birth_date and today."""
    years = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


@dataclass(frozen=True)
class PersonProfile:
    """A person who can use the scale."""

    profile_id: str
    display_name: str
    height_cm: float
    sex: str
    age: int | None = None
    birth_date: date | None = None
    athlete: bool = False
    person_entity: str | None = None
    expected_weight_kg: float | None = None

    def current_age(self, today: date) -> int:
        """Return age in years, derived from birth_date when set."""
        if self.birth_date is not None:
            return age_from_birth_date(self.birth_date, today)
        return self.age if self.age is not None else 30

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PersonProfile:
        """Build a profile from its stored options dict."""
        raw_birth = data.get("birth_date")
        return cls(
            profile_id=data["profile_id"],
            display_name=data["display_name"],
            height_cm=float(data["height_cm"]),
            sex=data["sex"],
            age=data.get("age"),
            birth_date=date.fromisoformat(raw_birth) if raw_birth else None,
            athlete=bool(data.get("athlete", False)),
            person_entity=data.get("person_entity") or None,
            expected_weight_kg=data.get("expected_weight_kg"),
        )


@dataclass(frozen=True)
class Candidate:
    """Distance of a reading from one person's expected weight."""

    profile_id: str
    distance_kg: float
    within_tolerance: bool


@dataclass(frozen=True)
class Attribution:
    """Outcome of scoring one reading."""

    profile_id: str | None
    candidates: list[Candidate] = field(default_factory=list)
    reason: str = "pending"


def ewma(history: list[float]) -> float:
    """Return the exponentially weighted mean of a non-empty history."""
    value = history[0]
    for sample in history[1:]:
        value = EWMA_ALPHA * sample + (1 - EWMA_ALPHA) * value
    return value


def update_expected_weight(
    history: list[float], weight_kg: float, history_size: int = DEFAULT_HISTORY_SIZE
) -> tuple[list[float], float]:
    """Append a reading to the history (capped) and return the EWMA."""
    new_history = [*history, weight_kg][-history_size:]
    return new_history, ewma(new_history)


def tolerance_for(
    expected_kg: float,
    tolerance_kg: float = DEFAULT_TOLERANCE_KG,
    tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
) -> float:
    """Return the match tolerance: max(fixed kg, percentage of expected)."""
    return max(tolerance_kg, expected_kg * tolerance_pct / 100.0)


def score(
    weight_kg: float,
    profiles: list[PersonProfile],
    expected_weights: dict[str, float],
    *,
    excluded: set[str] | None = None,
    force_profile_id: str | None = None,
    tolerance_kg: float = DEFAULT_TOLERANCE_KG,
    tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
    margin_kg: float = DEFAULT_MARGIN_KG,
) -> Attribution:
    """Attribute a reading to a profile or leave it pending.

    A forced profile wins over scoring. Excluded profiles (for example
    someone not home) are never auto-assigned. A single eligible profile
    receives the reading without scoring. Otherwise the closest profile
    within tolerance wins when it is at least margin_kg closer than the
    runner-up. Profiles with no expected weight cannot be scored.
    """
    excluded = excluded or set()
    ids = {p.profile_id for p in profiles}

    if force_profile_id is not None and force_profile_id in ids:
        return Attribution(force_profile_id, [], "forced")

    eligible = [p for p in profiles if p.profile_id not in excluded]
    if not eligible:
        return Attribution(None, [], "no_eligible_person")

    if len(profiles) == 1 and eligible:
        return Attribution(eligible[0].profile_id, [], "single_person")

    candidates: list[Candidate] = []
    for profile in eligible:
        expected = expected_weights.get(profile.profile_id)
        if expected is None:
            continue
        candidates.append(
            Candidate(
                profile.profile_id,
                abs(weight_kg - expected),
                abs(weight_kg - expected)
                <= tolerance_for(expected, tolerance_kg, tolerance_pct),
            )
        )
    candidates.sort(key=lambda c: c.distance_kg)

    if not candidates or not candidates[0].within_tolerance:
        return Attribution(None, candidates, "no_match")

    best = candidates[0]
    if len(candidates) > 1 and candidates[1].distance_kg - best.distance_kg < margin_kg:
        return Attribution(None, candidates, "ambiguous")
    return Attribution(best.profile_id, candidates, "weight_match")


def confidence_for(result: Attribution, margin_kg: float = DEFAULT_MARGIN_KG) -> float:
    """Return 0..1 confidence: 1.0 unless two people were close in weight."""
    if result.profile_id is None:
        return 0.0
    if result.reason in ("forced", "single_person") or len(result.candidates) < 2:
        return 1.0
    gap = result.candidates[1].distance_kg - result.candidates[0].distance_kg
    return round(min(1.0, gap / (2 * margin_kg)), 2)
