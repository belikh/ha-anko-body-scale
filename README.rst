.. raw:: html

   <p align="right">
     <picture>
       <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/belikh/design/latest/packages/graphics/logo/jupiter-logo-dark.svg">
       <img alt="jupiter.au" src="https://raw.githubusercontent.com/belikh/design/latest/packages/graphics/logo/jupiter-logo-light.svg" width="260">
     </picture>
   </p>

   <h1>ANKO Body Scale for Home Assistant</h1>

.. meta::
   :description: Home Assistant custom integration for the ANKO iF1012D Bluetooth body scale (IF_B7), sold by Kmart Australia, using passive BLE advertisements.

A custom integration for the **ANKO iF1012D Bluetooth body scale** (advertised
as ``IF_B7``) in Home Assistant. ANKO is Kmart Australia's own brand, so this is
the Kmart Bluetooth body scale. It listens passively to the scale's BLE
advertisements — no connection, no polling, no cloud account — decodes weight,
bioelectrical impedance and reading stability directly from the manufacturer
data, and computes the full body-composition suite (body fat, muscle mass,
bone mass, body water, basal metabolic rate, metabolic age, visceral fat index
and ideal weight range) from the height / age / sex profile you enter at setup.

The advertisement layout was reverse engineered from the MovingLife app and
confirmed against nRF Connect captures (Senssun protocol family).

`Features`_ ·
`Installation`_ ·
`Setup`_ ·
`How readings are assigned`_ ·
`Entities`_ ·
`How body composition is calculated`_ ·
`Actions`_

|

.. raw:: html

   <p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/belikh/design/latest/packages/github/graphics/rule/end-dark.svg"><img alt="" src="https://raw.githubusercontent.com/belikh/design/latest/packages/github/graphics/rule/end-light.svg" width="50%"></picture></p>

|

Features
--------

- Setup through the UI with Bluetooth discovery.
- Passive BLE: the scale broadcasts and Home Assistant listens. Nothing is sent to the internet.
- Body composition: 14 sensors computed from each settled reading. Fat-free mass uses a published foot-to-foot impedance equation, with a BMI-based fallback (see `How body composition is calculated`_).
- Multiple people and multiple scales. People are defined once and shared by every scale. Each reading goes to the person whose recent weights are closest (see `How readings are assigned`_). Each scale can be limited to some of the people (see `Several scales`_).
- One device per person, shared by all scales. Each scale device keeps its weight, raw impedance and reading-stable entities.
- Settling buffer: one weigh-in produces one set of values, not one per advert.
- Expected weights and the pending queue persist across restarts.
- Ambiguous readings wait as pending measurements, with services, events and optional mobile notifications to resolve them.
- Redacted diagnostics download.

|

Installation
------------

.. image:: https://my.home-assistant.io/badges/hacs_repository.svg
   :alt: Add to Home Assistant
   :target: https://my.home-assistant.io/redirect/hacs_repository/?owner=belikh&repository=ha-anko-body-scale&category=integration

1. Click the **Add to Home Assistant** button above and choose **Download**,
   or search for **ANKO Body Scale** in the Marketplace or HACS.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services**, add **ANKO Body Scale** and pick
   the scale from the list.

Manual
~~~~~~

1. Download the ``custom_components/anko_scale`` folder from this repository.
2. Copy it into the ``custom_components`` directory of your Home Assistant
   configuration.
3. Restart Home Assistant.

Custom repository (fallback)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If the search returns nothing, open the Marketplace or HACS, use the three dots
(top right) → **Custom repositories**, add
``https://github.com/belikh/ha-anko-body-scale`` with category **Integration**, then
install **ANKO Body Scale** and restart Home Assistant.

|

Setup
-----

1. Go to **Settings → Devices & Services → Add Integration** and search for **ANKO Body Scale**. If the scale is powered and in range, Home Assistant usually shows a discovery card.
2. For manual setup, pick the scale (advertised as ``IF_B7``) from the list of previously seen devices.
3. Enter the first person: name, height, sex, and either a birth date or an age. Optional fields: a ``person`` entity and a starting weight.
4. The scale device and the person device appear with their entities. The first setup also creates a second entry, **ANKO Body Scale people**, which holds the people list.

Step on the scale barefoot and stand still until the reading settles.

Upgrading from earlier versions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

On the first start of 2.0.0 the integration creates the **ANKO Body Scale people** entry and moves each scale's people into it. Entity IDs, entity history and person devices stay the same. A v1 profile becomes **Person 1** (profile ID ``legacy``). Person entity unique IDs change from ``<address>_<person>_<key>`` to ``person_<person>_<key>``. A scale's own entities (for example ``sensor.anko_body_scale_weight``) are untouched.

If two scales had a person with the same name, they become one person. The weight history of the first scale is kept and the other is dropped (a warning is logged). A scale that had every person follows the full list, so people added later can use it. Otherwise it keeps exactly the people it had before.

During the first start a scale entry can show "retrying" for a few seconds while the People entry loads.

Configure
~~~~~~~~~

**Configure** on the **ANKO Body Scale people** entry opens a menu:

.. list-table::
   :header-rows: 1

   * - Item
     - What it does
   * - |i-edit-l| |i-edit-d| Add a person
     - Name, height, sex, birth date (typed as YYYY-MM-DD) or age, optional ``person`` entity, optional starting weight.
   * - |i-edit-l| |i-edit-d| Add from a Home Assistant person
     - Pick a ``person`` entity. The new profile takes its name and skips them when they are ``not_home``.
   * - |i-edit-l| |i-edit-d| Edit a person
     - Changes the same fields. The profile ID, and so the entity IDs, stay the same.
   * - |i-edit-l| |i-edit-d| Delete a person
     - Removes their device and entities. At least one person must remain.
   * - |i-edit-l| |i-edit-d| Attribution settings
     - Tolerance, margin, history size, pending timeout and an optional notify action. They apply to all scales.

**Configure** on a scale entry lists the people who use that scale.

Saving reloads the entry. People added or deleted show up or disappear after the reload.

Several scales
~~~~~~~~~~~~~~

Add each scale through **Add Integration**. When two or more people exist, the setup asks who uses the new scale.

.. list-table::
   :header-rows: 1

   * - Scale setting
     - Result
   * - |i-sliders-l| |i-sliders-d| Everyone selected (default)
     - Any person can be weighed on the scale, including people added later.
   * - |i-sliders-l| |i-sliders-d| Some people selected
     - Only those people are matched on this scale. People added later are not included until you select them.
   * - |i-sliders-l| |i-sliders-d| One person selected
     - Every reading on the scale goes to that person, with no matching.

Deleting a person removes them from every scale's list. A scale left with no people holds its readings as pending until you pick people under **Configure** on that scale.

A person weighed on any scale updates the same sensors and weight history. The **Weighing in** button arms the next reading on every scale that allows the person. Scale actions (``assign_measurement``, ``discard_measurement``, ``set_next_person``, ``capture_measurement``) need ``config_entry_id`` when more than one scale exists. ``reassign_measurement`` and ``reset_person_history`` act on people and never need it.

|

How readings are assigned
-------------------------

Weight and impedance come from the scale. The scale does not say who is standing on it, so the integration chooses.

1. A reading counts once it has 3 stable adverts within 0.5 kg and 5 s. If the scale goes quiet after fewer adverts, the last stable ones are used.
2. With one person configured, that person gets the reading.
3. With several, each person has an expected weight: an exponentially weighted average (alpha 0.3) of their last readings, up to 50. The starting weight seeds it.
4. The closest person wins if the reading is within ``max(tolerance kg, tolerance % of expected)`` (defaults 5 kg and 7 %) and at least the margin (default 2 kg) closer than the next person.
5. Anything else becomes a **pending measurement**. No per-person values are published for it.

People whose ``person`` entity is ``not_home`` are never auto-assigned. A person with no history and no starting weight cannot be matched by weight: use the **Weighing in** button for their first readings.

Overrides
~~~~~~~~~

- **Weighing in** button (per person) and the **Next person** select (on the scale device) send the next settled reading to that person, even if weights overlap. The override lasts 60 s or one reading.
- A forced reading also counts toward that person's expected weight, which seeds new people without typing a weight.

Pending measurements
~~~~~~~~~~~~~~~~~~~~

A pending measurement is kept for the pending timeout (default 60 min, 10 at most). Resolve it with ``anko_scale.assign_measurement``, or ``anko_scale.discard_measurement`` for a guest. Guests never create a profile. The ``pending_id`` is in the attributes of ``sensor.anko_body_scale_pending_measurements`` and in the ``anko_scale_pending_measurement`` event.

If **Notify action** is set (for example ``notify.mobile_app_phone``), the phone gets a notification with an "I'm <name>" action for up to two candidates and a "Not me" action that discards. A persistent notification is always created.

Unknown weights
~~~~~~~~~~~~~~~

When there are two or more people and a weigh-in is outside everyone's tolerance, the integration creates a repair under **Settings → System → Repairs**: "A weigh-in matched nobody". **Fix** opens a form to add that person with the observed weight as their starting weight. Submitting adds the person, reloads the entry and drops the pending weigh-in. The next weigh-in is the first one published for them. Each detection is logged at info level and counted in the diagnostics (``unknown_weights``). With one person configured there are no repairs: that person gets every reading. A weight that is close to two people (ambiguous) creates a pending measurement but no repair.

|

Entities
--------

Scale device (``ANKO Body Scale``):

.. list-table::
   :header-rows: 1

   * - Platform
     - Entity
     - Category
     - Default
     - Description
   * - |i-pulse-l| |i-pulse-d| ``sensor``
     - Weight
     - —
     - enabled
     - Latest advert weight in kg
   * - |i-pulse-l| |i-pulse-d| ``sensor``
     - Impedance (raw)
     - Diagnostic
     - **disabled**
     - Raw impedance code from the scale, no unit. 0 means the feet were not touching the pads.
   * - |i-pulse-l| |i-pulse-d| ``sensor``
     - Last person
     - —
     - enabled
     - Name of the person the last weigh-in went to
   * - |i-pulse-l| |i-pulse-d| ``sensor``
     - Pending measurements
     - Diagnostic
     - enabled
     - Count of unassigned weigh-ins, with their IDs in attributes
   * - |i-check-l| |i-check-d| ``binary_sensor``
     - Reading stable
     - Diagnostic
     - enabled
     - ``on`` when the scale has finished measuring (status byte ``0xA1``)
   * - |i-filter-l| |i-filter-d| ``select``
     - Next person
     - —
     - enabled
     - One-shot manual assignment

Each person device (shared by all scales) has 14 sensors (``sensor.<name>_weight``, ``sensor.<name>_body_fat``, and so on) with values from that person's last assigned weigh-in, plus a ``button`` **Weighing in**. The scale device carries no body-composition sensors.

.. list-table::
   :header-rows: 1

   * - Sensor
     - Description
   * - |i-pulse-l| |i-pulse-d| Weight
     - Weight in kg
   * - |i-pulse-l| |i-pulse-d| Impedance (raw)
     - Raw code from the scale (disabled by default)
   * - |i-pulse-l| |i-pulse-d| BMI
     - Body mass index
   * - |i-pulse-l| |i-pulse-d| Body fat
     - Percentage
   * - |i-pulse-l| |i-pulse-d| Fat mass
     - kg
   * - |i-pulse-l| |i-pulse-d| Lean mass
     - Fat-free mass in kg
   * - |i-pulse-l| |i-pulse-d| Muscle mass
     - kg
   * - |i-pulse-l| |i-pulse-d| Body water
     - Percentage
   * - |i-pulse-l| |i-pulse-d| Bone mass
     - kg
   * - |i-pulse-l| |i-pulse-d| Basal metabolic rate
     - kcal/day (Mifflin-St Jeor)
   * - |i-pulse-l| |i-pulse-d| Metabolic age
     - Years
   * - |i-pulse-l| |i-pulse-d| Visceral fat index
     - 1 to 30 heuristic
   * - |i-pulse-l| |i-pulse-d| Ideal weight (min), (max)
     - Healthy range for the height (BMI 18.5 to 24.9), diagnostic

|

How body composition is calculated
----------------------------------

.. list-table::
   :header-rows: 1

   * - Value
     - Method
     - Source
   * - |i-chart-l| |i-chart-d| Fat-free mass, body fat, fat mass, lean mass
     - ``13.055 + 0.204·weight + 0.394·height²/impedance − 0.136·age + 8.125·(male=1)``
     - Wu et al., Nutr J 2015;14:52. Foot-to-foot, 554 Taiwanese adults aged 16 to 75, DXA reference, SEE 3.17 kg
   * - |i-chart-l| |i-chart-d| Body fat fallback
     - ``1.20·BMI + 0.23·age − 10.8·(male=1) − 5.4`` (under 16: ``1.51·BMI − 0.70·age − 3.6·(male=1) + 1.4``)
     - Deurenberg et al., Br J Nutr 1991;65:105. SEE 4.1 %
   * - |i-chart-l| |i-chart-d| Basal metabolic rate
     - Mifflin-St Jeor
     - Mifflin et al., Am J Clin Nutr 1990
   * - |i-chart-l| |i-chart-d| Body water
     - 73.2 % of fat-free mass
     - Pace & Rathbun, J Biol Chem 1945
   * - |i-chart-l| |i-chart-d| Muscle mass, bone mass, visceral fat index, metabolic age
     - Heuristics. No published consumer-scale equation exists.
     - Treat as trends, not measurements

The scale does not report ohms. Byte 13 of its advert is a raw code that is 0 without foot contact and rose with body size in the frames captured so far (117 to 128 for a 61.5 kg man, 165 for a 71.65 kg man). The conversion to ohms is unknown, so the integration multiplies the code by 2.56 as an assumption (the scaling 1.x used). Results from that route carry ``method: bia_assumed``. Treat them as provisional until the conversion is calibrated against known resistors.

The impedance equation is used only when the impedance is between 325 and 735 Ω (the range Wu et al. observed), the person is 16 or older, and the result is between 50 % and 95 % of body weight. Otherwise body fat comes from BMI. Each body-composition sensor has a ``method`` attribute: ``bia_assumed`` or ``bmi``. With no foot contact (raw code 0) the weight is still recorded and the method is ``bmi``.

If a person always gets ``bmi``, the assumed impedance is outside that range or the feet are missing the pads. Wet feet lower the reading; dry, bare feet on both pad pairs give the best contact.

Foot-to-foot impedance gives an individual body-fat error of roughly ±5 percentage points.

|

Actions
-------

``assign_measurement``, ``discard_measurement``, ``set_next_person`` and ``capture_measurement`` take an optional ``config_entry_id``, needed only with more than one scale. ``reassign_measurement`` and ``reset_person_history`` do not.

.. list-table::
   :header-rows: 1

   * - Action
     - Fields
     - Effect
   * - |i-bolt-l| |i-bolt-d| ``anko_scale.assign_measurement``
     - ``pending_id``, ``person_id``
     - Publishes the pending weigh-in for that person and fires ``anko_scale_weigh_in``.
   * - |i-bolt-l| |i-bolt-d| ``anko_scale.discard_measurement``
     - ``pending_id``
     - Drops a pending weigh-in. Admin users only.
   * - |i-bolt-l| |i-bolt-d| ``anko_scale.reassign_measurement``
     - ``person_id``
     - Moves the last attributed weigh-in to another person and restores the previous owner's values. Not available after a restart.
   * - |i-bolt-l| |i-bolt-d| ``anko_scale.capture_measurement``
     - ``timeout`` (5 to 300 s, default 60)
     - Waits for the next settled weigh-in and returns ``weight_kg`` and ``timestamp`` as the action response. The reading is not assigned and nothing enters anyone's history. Fails with an error at the timeout.
   * - |i-bolt-l| |i-bolt-d| ``anko_scale.set_next_person``
     - ``person_id`` (empty clears)
     - Same as the **Weighing in** button.
   * - |i-bolt-l| |i-bolt-d| ``anko_scale.reset_person_history``
     - ``person_id``
     - Clears the stored weights; the starting weight, if set, is used again. Admin users only.

|

Events
------

``anko_scale_weigh_in`` fires once per attributed weigh-in:

.. code-block:: yaml

   person_id: jupiter
   person_name: Jupiter
   weight_kg: 81.2
   impedance_raw: 165        # raw code, empty when the feet missed the pads
   confidence: 1.0        # 0..1, lower when two people were close in weight
   source: weight_match   # weight_match, single_person, forced, assigned, reassigned
   timestamp: "2026-11-07T02:40:11+00:00"
   entry_id: 01KV25DSCCM1DXPM40CFMM4H0W

``anko_scale_pending_measurement`` fires when a reading cannot be assigned. It carries ``pending_id``, ``weight_kg``, ``impedance_raw``, ``candidates`` (person IDs with ``distance_kg``) and ``reason`` (``ambiguous``, ``no_match`` or ``no_eligible_person``).

Example automation:

.. code-block:: yaml

   triggers:
     - trigger: event
       event_type: anko_scale_weigh_in
       event_data:
         person_id: jupiter
   actions:
     - action: notify.mobile_app_phone
       data:
         message: "{{ trigger.event.data.person_name }}: {{ trigger.event.data.weight_kg }} kg"

Example dashboard card:

.. code-block:: yaml

   type: entities
   title: Weigh-ins
   entities:
     - sensor.jupiter_weight
     - sensor.jupiter_body_fat
     - sensor.sarah_weight
     - sensor.sarah_body_fat
     - sensor.anko_body_scale_pending_measurements
     - select.anko_body_scale_next_person

Entity IDs follow the names you choose.

.. raw:: html

   <table>
     <tr align="left"><th>Note</th></tr>
     <tr><td>

Body-composition values from any single-frequency, foot-to-foot
BIA device are estimates (typically within ±3–8 % of a DEXA scan) — the same
caveat applies to premium smart scales using the same equations. Weight,
impedance and reading stability are direct from the scale; everything else is
computed.

.. raw:: html

     </td></tr>
   </table>

|

Troubleshooting
---------------

- **No ANKO scales found during setup** — the scale must be powered, out of
  its sleep state and in Bluetooth range during setup. Step on it briefly to
  wake it, or check it appears under **Settings → Devices & Services →
  Bluetooth**. A Bluetooth proxy (e.g. ESPHome) also works if the adapter is
  far away.
- **Sensors stay unknown / unavailable** — no stable reading has been
  received yet. The body-composition sensors only fill in when the reading is
  stable and carries a valid impedance. Step on the scale barefoot, stand
  still, and wait for the stable reading; the ``reading_stable`` binary sensor
  shows whether the last advertisement was settled.
- **Weight shows but body fat does not** — weight comes from every
  advertisement, body composition needs a settled impedance (``0x0001`` is the
  settling sentinel). This is normal while the reading is still settling.
- **Body composition looks off** — check the person's details under **Configure → Edit a person**. BIA maths depends heavily on height and age; bare feet
  and dry skin also matter.
- **Readings stop after Home Assistant restarts** — the passive listener
  restarts with the entry. If the scale is out of range the last values are
  restored and marked available until a fresh reading arrives; step on the
  scale to refresh them.

|

Examples
--------

The ``examples/`` folder holds copy-and-edit files. None are installed or enabled by default.

.. list-table::
   :header-rows: 1

   * - File
     - What it does
   * - |i-file-l| |i-file-d| `examples/dashboard.yaml <examples/dashboard.yaml>`__
     - Dashboard with a per-person view (weight, body fat, muscle, BMR, metabolic age, visceral fat, goal) and a scale view. Paste it into the raw configuration editor of a new dashboard.
   * - |i-file-l| |i-file-d| `examples/weight_loss_leaderboard.yaml <examples/weight_loss_leaderboard.yaml>`__
     - Statistics sensors for 30-day weight change plus a template sensor that ranks everyone by kilograms lost and percentage of their goal. Ties share a rank; people without data are listed last.
   * - |i-file-l| |i-file-d| `examples/pet_weighing.yaml <examples/pet_weighing.yaml>`__
     - Script that talks you through two weigh-ins with TTS (holding the pet, then alone), stores the difference in a helper and announces it. Uses ``anko_scale.capture_measurement``, so nobody's history changes.

The leaderboard reads health data from your own Home Assistant only. Nothing leaves it unless you share the dashboard. The examples use entity IDs for people named Jupiter and Sarah; replace them with yours. Screenshots are not included.

|

Diagnostics
-----------

**Settings → Devices & Services → ANKO Body Scale → Download diagnostics** includes the integration version, options with names, birth dates and the BLE address redacted, per-person history length and last timestamp, advert counts, RSSI, the last raw frame and the last 30 distinct raw adverts. It contains no weight history.

|

Reporting a problem
-------------------

`Open an issue <https://github.com/belikh/ha-anko-body-scale/issues/new/choose>`__ and
fill in the bug report form. It asks for the scale model and the debug log:

1. **Debug log.** Open **Settings > Devices & services > ANKO Body Scale**,
   choose **Enable debug logging** from the three-dot menu, repeat the problem,
   then choose **Disable debug logging**. The browser downloads
   ``home-assistant_anko_scale_<date>.log``. The log holds only the period
   between the two clicks, but it can include your Bluetooth address, so read
   the file before posting.

To keep debug logging on across restarts, add this to ``configuration.yaml``:

.. code-block:: yaml

   logger:
     logs:
       custom_components.anko_scale: debug

|

Known limitations
-----------------

- **Attribution is by weight.** People within a few kg of each other, such as
  a parent and a teenager, produce pending measurements until you use the
  **Weighing in** button or the person entity filter.
- **Barefoot impedance.** Socks or dry skin raise impedance and skew body fat for any person.
- **Single-frequency BIA only.** The scale reports one impedance value; the
  integration cannot segment limbs or use multi-frequency analysis.
- **Passive listening only.** The scale is never connected to — Home Assistant
  cannot trigger a weigh-in or read history; it only sees advertisements
  broadcast while you step on the scale.

|

Remove
------

Open **Settings → Devices & Services**, open the **ANKO Body Scale**
entry, click the three dots → **Delete**. This removes the config entry, its
device and entities. Optionally also remove the integration files (Marketplace/HACS or
``custom_components/anko_scale``) and restart Home Assistant.

|

Develop
-------

Tests run against a pinned Home Assistant version with
`uv <https://docs.astral.sh/uv/>`__:

.. code-block:: sh

   uv sync          # create .venv from uv.lock
   uv run pytest
   uv run ruff check custom_components tests
   uv run mypy

``pyproject.toml`` carries the dev dependency group (pytest-homeassistant-custom-component,
ruff, mypy) and ``uv.lock`` pins the full tree, so the suite is reproducible.

|

Licence
-------

MIT. See `LICENSE <LICENSE>`__.

|

Credits
-------

- **Jupiter Belic** — integration author. The advertisement layout was reverse
  engineered from the MovingLife app and confirmed against nRF Connect captures.
- Body-composition equations (see ``body_metrics.py``):

  - **Mifflin et al.**, *A new predictive equation for resting energy
    expenditure*, Am J Clin Nutr 1990 (BMR).

  - **Wu et al.**, Nutr J 2015;14:52 (fat-free mass from foot-to-foot
    impedance).

  - **Deurenberg et al.**, Br J Nutr 1991;65:105 (body fat from BMI).

  - **Pace & Rathbun**, J Biol Chem 1945 (total body water ≈ 73 % of fat-free
    mass).

  - **American Council on Exercise** reference ranges for body fat percentage.

|

.. raw:: html

   <p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/belikh/design/latest/packages/github/graphics/rule/end-dark.svg"><img alt="" src="https://raw.githubusercontent.com/belikh/design/latest/packages/github/graphics/rule/end-light.svg" width="50%"></picture></p>

|

.. raw:: html

   <p align="right"><sub>jupiter.au</sub></p>

.. |i-bolt-l| image:: https://raw.githubusercontent.com/belikh/design/latest/packages/github/graphics/icon/bolt-light.svg#gh-light-mode-only
   :width: 20
   :alt:
.. |i-bolt-d| image:: https://raw.githubusercontent.com/belikh/design/latest/packages/github/graphics/icon/bolt-dark.svg#gh-dark-mode-only
   :width: 20
   :alt:
.. |i-chart-l| image:: https://raw.githubusercontent.com/belikh/design/latest/packages/github/graphics/icon/chart-light.svg#gh-light-mode-only
   :width: 20
   :alt:
.. |i-chart-d| image:: https://raw.githubusercontent.com/belikh/design/latest/packages/github/graphics/icon/chart-dark.svg#gh-dark-mode-only
   :width: 20
   :alt:
.. |i-check-l| image:: https://raw.githubusercontent.com/belikh/design/latest/packages/github/graphics/icon/check-light.svg#gh-light-mode-only
   :width: 20
   :alt:
.. |i-check-d| image:: https://raw.githubusercontent.com/belikh/design/latest/packages/github/graphics/icon/check-dark.svg#gh-dark-mode-only
   :width: 20
   :alt:
.. |i-edit-l| image:: https://raw.githubusercontent.com/belikh/design/latest/packages/github/graphics/icon/edit-light.svg#gh-light-mode-only
   :width: 20
   :alt:
.. |i-edit-d| image:: https://raw.githubusercontent.com/belikh/design/latest/packages/github/graphics/icon/edit-dark.svg#gh-dark-mode-only
   :width: 20
   :alt:
.. |i-file-l| image:: https://raw.githubusercontent.com/belikh/design/latest/packages/github/graphics/icon/file-light.svg#gh-light-mode-only
   :width: 20
   :alt:
.. |i-file-d| image:: https://raw.githubusercontent.com/belikh/design/latest/packages/github/graphics/icon/file-dark.svg#gh-dark-mode-only
   :width: 20
   :alt:
.. |i-filter-l| image:: https://raw.githubusercontent.com/belikh/design/latest/packages/github/graphics/icon/filter-light.svg#gh-light-mode-only
   :width: 20
   :alt:
.. |i-filter-d| image:: https://raw.githubusercontent.com/belikh/design/latest/packages/github/graphics/icon/filter-dark.svg#gh-dark-mode-only
   :width: 20
   :alt:
.. |i-pulse-l| image:: https://raw.githubusercontent.com/belikh/design/latest/packages/github/graphics/icon/pulse-light.svg#gh-light-mode-only
   :width: 20
   :alt:
.. |i-pulse-d| image:: https://raw.githubusercontent.com/belikh/design/latest/packages/github/graphics/icon/pulse-dark.svg#gh-dark-mode-only
   :width: 20
   :alt:
.. |i-sliders-l| image:: https://raw.githubusercontent.com/belikh/design/latest/packages/github/graphics/icon/sliders-light.svg#gh-light-mode-only
   :width: 20
   :alt:
.. |i-sliders-d| image:: https://raw.githubusercontent.com/belikh/design/latest/packages/github/graphics/icon/sliders-dark.svg#gh-dark-mode-only
   :width: 20
   :alt:
