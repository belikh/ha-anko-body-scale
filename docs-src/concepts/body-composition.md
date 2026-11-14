---
title: How body composition is calculated
summary: The equation behind each body-composition sensor, its source and its error.
order: 20
audience: users
status: draft
---

Weight and the raw impedance code come from the scale. Every other value is computed from them and the person's height, age and sex.

| Value | Method | Source |
| --- | --- | --- |
| Lean mass | `13.055 + 0.204·weight + 0.394·height²/impedance − 0.136·age + 8.125·male` | Wu et al., Nutr J 2015;14:52. Foot-to-foot [[term:BIA]], 554 Taiwanese adults aged 16 to 75, DXA reference, standard error 3.17 kg. |
| Body fat, fat mass | Weight minus lean mass | Derived. |
| Body fat fallback | `1.20·BMI + 0.23·age − 10.8·male − 5.4` | Deurenberg et al., Br J Nutr 1991;65:105. Standard error 4.1 %. |
| Body fat fallback, under 16 | `1.51·BMI − 0.70·age − 3.6·male + 1.4` | Deurenberg et al. Standard error 4.4 %. |
| Body water | 73.2 % of lean mass | Pace and Rathbun, J Biol Chem 1945. |
| Basal metabolic rate | `10·weight + 6.25·height − 5·age + 5` for men, `− 161` for women | Mifflin et al., Am J Clin Nutr 1990. |
| Bone mass | 5.21 % of lean mass for men, 4.90 % for women | Heuristic. |
| Muscle mass | Lean mass minus bone mass | Heuristic. |
| Metabolic age | Age plus one year per point of body fat above 19 % (men) or 28 % (women), 15 at least | Heuristic. The midpoints follow the American Council on Exercise ranges. |
| Visceral fat index | `1.5·(BMI − 22) + 0.1·age + 2·male`, limited to 1 to 30 | Heuristic. |
| Ideal weight (min), (max) | BMI 18.5 and 24.9 at the person's height | Derived. |

Weight is in kg, height in cm, impedance in ohm, and `male` is 1 for men and 0 for women. No published equation exists for the four heuristic values on a consumer scale. Read them as trends.

## The impedance route

The scale does not report ohms. Byte 13 of its advert is a raw code. The code is 0 without foot contact. It was 117 to 128 for a 61.5 kg man and 165 for a 71.65 kg man in the frames captured so far.

The conversion to ohms is unknown. The integration multiplies the code by 2.56, the scaling that version 1 used. Results from this route carry `method: bia_assumed`. Treat them as provisional until the conversion is calibrated against known resistors.

The integration uses the impedance equation when all three conditions hold:

- The assumed impedance is between 325 and 735 ohm, the range Wu et al. observed. That is a raw code of 127 to 287.
- The person is 16 or older.
- The lean mass is between 50 % and 95 % of the weight.

## The BMI route

When a condition fails, body fat comes from the Deurenberg equation, limited to 3 % to 60 %. The sensors carry `method: bmi`. A weigh-in with no foot contact still records the weight and uses this route.

## Accuracy

Foot-to-foot impedance at one frequency gives an individual body-fat error of about ±5 percentage points against a DXA scan. The BMI route does not see muscle, so it reads high for muscular people. Compare values from the same route over weeks, at the same time of day, with dry bare feet.

:::see-also
- [[reference/entities]]
- [[concepts/advert-format]]
- [[concepts/limitations]]
:::
