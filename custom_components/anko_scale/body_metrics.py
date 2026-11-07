"""Body-composition calculations for the ANKO/Senssun BLE scale.

Fat-free mass (FFM) comes from a foot-to-foot bioelectrical-impedance
equation. When the impedance is outside the range that equation was
validated on, or gives an FFM that cannot fit inside the body weight,
body fat is estimated from BMI instead. The result carries
``bia_valid`` (1.0 for the impedance route, 0.0 for the BMI route) so
callers can tell which one produced the numbers.

The impedance passed in for the ANKO iF1012D is an assumed value: the
scale sends a raw code, and its conversion to ohms has not been calibrated.

References:
  - FFM from foot-to-foot impedance: Wu et al., "Predicting body
    composition using foot-to-foot bioelectrical impedance analysis in
    healthy Asian individuals", Nutr J 2015;14:52. 554 Taiwanese adults,
    age 16-75, BMI 15.9-43.1, DXA reference, 50 kHz four-electrode
    platform. r2 0.92, SEE 3.17 kg. Observed foot-to-foot impedance
    326-733 ohm. The equation is a single device/population fit, so
    individual body-fat values carry roughly +/-5 percentage points.
  - BMI-based body fat: Deurenberg, Weststrate & Seidell, "Body mass
    index as a measure of body fatness: age- and sex-specific prediction
    formulas", Br J Nutr 1991;65:105-114. SEE 4.1 % (adults), 4.4 %
    (children).
  - BMR: Mifflin et al., Am J Clin Nutr 1990.
  - Total body water as a fraction of FFM (~73 %): Pace & Rathbun,
    J Biol Chem 1945.
  - Reference body-fat midpoints used for metabolic age: American Council
    on Exercise categories.
  - Bone mass, metabolic age and visceral fat index have no published
    consumer-scale equation. They are heuristics and are documented as
    such in the README.

"""

from __future__ import annotations

SEX_MALE = "male"
SEX_FEMALE = "female"

# Healthy body-fat-% midpoints by sex, used as the "metabolic age" reference.
_REFERENCE_BODY_FAT = {
    SEX_MALE: 19.0,
    SEX_FEMALE: 28.0,
}


# Range of foot-to-foot impedance the Wu et al. equation was fitted on.
WU_MIN_IMPEDANCE_OHM = 325.0
WU_MAX_IMPEDANCE_OHM = 735.0
WU_MIN_AGE = 16
# Share of body weight that fat-free mass may take before it is rejected.
MAX_FFM_FRACTION = 0.95
MIN_FFM_FRACTION = 0.5


def _wu_ffm(
    weight_kg: float, impedance_ohm: float, height_cm: float, age: int, is_male: bool
) -> float:
    """Return fat-free mass (kg) from Wu et al. 2015, equation 2."""
    return (
        13.055
        + 0.204 * weight_kg
        + 0.394 * (height_cm**2) / impedance_ohm
        - 0.136 * age
        + 8.125 * (1 if is_male else 0)
    )


def _deurenberg_body_fat(bmi: float, age: int, is_male: bool) -> float:
    """Return body fat % from BMI (Deurenberg et al. 1991)."""
    sex = 1 if is_male else 0
    if age < WU_MIN_AGE:
        return 1.51 * bmi - 0.70 * age - 3.6 * sex + 1.4
    return 1.20 * bmi + 0.23 * age - 10.8 * sex - 5.4


def calculate_metrics(
    weight_kg: float,
    impedance_ohm: float | None,
    height_cm: float,
    age: int,
    sex: str,
) -> dict[str, float]:
    """Compute the body-composition suite from one reading."""
    height_m = height_cm / 100.0
    is_male = sex == SEX_MALE

    bmi = weight_kg / (height_m**2)

    ffm: float | None = None
    if (
        impedance_ohm is not None
        and age >= WU_MIN_AGE
        and WU_MIN_IMPEDANCE_OHM <= impedance_ohm <= WU_MAX_IMPEDANCE_OHM
    ):
        candidate = _wu_ffm(weight_kg, impedance_ohm, height_cm, age, is_male)
        if MIN_FFM_FRACTION * weight_kg <= candidate <= MAX_FFM_FRACTION * weight_kg:
            ffm = candidate
    bia_valid = ffm is not None
    if ffm is None:
        fallback_bf = max(3.0, min(60.0, _deurenberg_body_fat(bmi, age, is_male)))
        ffm = weight_kg * (1 - fallback_bf / 100.0)

    fat_mass = weight_kg - ffm
    body_fat_percent = (fat_mass / weight_kg) * 100

    # Total body water is ~73% of fat-free mass (Pace & Rathbun).
    body_water_percent = (ffm * 0.732 / weight_kg) * 100

    # Heuristic (no published consumer-scale equation): bone mineral as a
    # fraction of FFM, with a small sex offset.
    bone_fraction = 0.0521 if is_male else 0.0490
    bone_mass = ffm * bone_fraction

    # Muscle mass = fat-free mass minus bone mineral mass.
    muscle_mass = ffm - bone_mass

    # BMR: Mifflin-St Jeor.
    if is_male:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

    # Metabolic age: shift actual age by how far body fat % sits from
    # the sex-reference midpoint (1 year per percentage point).
    reference_bf = _REFERENCE_BODY_FAT[sex]
    metabolic_age = max(15, age + (body_fat_percent - reference_bf))

    # Heuristic (no published equation): visceral fat index on a 1-30 scale
    # from BMI, age and sex -- no waist measurement is available.
    visceral_fat = 1.5 * (bmi - 22) + 0.1 * age + (2 if is_male else 0)
    visceral_fat = max(1, min(30, visceral_fat))

    # Healthy weight range for this height (BMI 18.5-24.9).
    ideal_weight_min = 18.5 * height_m**2
    ideal_weight_max = 24.9 * height_m**2

    return {
        "bmi": round(bmi, 1),
        "body_fat_percent": round(body_fat_percent, 1),
        "fat_mass_kg": round(fat_mass, 2),
        "lean_mass_kg": round(ffm, 2),
        "muscle_mass_kg": round(muscle_mass, 2),
        "body_water_percent": round(body_water_percent, 1),
        "bone_mass_kg": round(bone_mass, 2),
        "bmr": round(bmr, 0),
        "metabolic_age": round(metabolic_age, 0),
        "visceral_fat_index": round(visceral_fat, 1),
        "ideal_weight_min_kg": round(ideal_weight_min, 1),
        "ideal_weight_max_kg": round(ideal_weight_max, 1),
        "bia_valid": 1.0 if bia_valid else 0.0,
    }
