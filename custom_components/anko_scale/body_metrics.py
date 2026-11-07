"""Body-composition (BIA) calculations for the ANKO/Senssun BLE scale.

These are standard published regression equations used by consumer
bioelectrical-impedance scales -- the same family of formulas used
inside $200-$600 "smart" scales. Accuracy versus a DEXA scan is
inherently +/-3-8% for any single-frequency foot-to-foot BIA device,
premium or not.

References:
  - BMR: Mifflin et al., "A new predictive equation for resting energy
    expenditure", Am J Clin Nutr 1990.
  - Fat-free mass from resistance index: Kyle et al., "Bioelectrical
    impedance analysis", Clin Nutr 2001 (reactance term omitted -- not
    available from a single-frequency foot-to-foot measurement).
  - Total body water as a fraction of fat-free mass (~73%): Pace &
    Rathbun, J Biol Chem 1945.
  - Healthy body-fat-% reference ranges: American Council on Exercise.

"""

from __future__ import annotations

SEX_MALE = "male"
SEX_FEMALE = "female"

# Healthy body-fat-% midpoints by sex, used as the "metabolic age" reference.
_REFERENCE_BODY_FAT = {
    SEX_MALE: 19.0,
    SEX_FEMALE: 28.0,
}


def calculate_metrics(
    weight_kg: float,
    impedance_ohm: float,
    height_cm: float,
    age: int,
    sex: str,
) -> dict[str, float]:
    """Compute the full body-composition suite from a single BIA reading."""
    height_m = height_cm / 100.0
    is_male = sex == SEX_MALE

    bmi = weight_kg / (height_m**2)

    # Resistance index: the standard BIA predictor variable.
    resistance_index = (height_cm**2) / impedance_ohm

    # Fat-free mass (Kyle et al. 2001, single-frequency simplification).
    ffm = (
        -4.104
        + 0.518 * resistance_index
        + 0.231 * weight_kg
        + 4.229 * (1 if is_male else 0)
    )
    # Sanity clamp: FFM must be a plausible fraction of total weight.
    ffm = max(0.5 * weight_kg, min(ffm, 0.95 * weight_kg))

    fat_mass = weight_kg - ffm
    body_fat_percent = (fat_mass / weight_kg) * 100

    # Total body water is ~73% of fat-free mass (Pace & Rathbun).
    body_water_percent = (ffm * 0.732 / weight_kg) * 100

    # Bone mineral mass as a fraction of FFM, with a small sex offset
    # (women average ~10% lower bone density than men).
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

    # Visceral fat index (1-30 scale, Omron/Tanita-style heuristic)
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
    }
