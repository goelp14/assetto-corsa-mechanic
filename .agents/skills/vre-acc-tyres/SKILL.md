---
name: vre-acc-tyres
description: Use for ACC GT3 tyre pressures, temps, graining, and cold-stint behaviour (ferrari_296_gt3 and other ACC GT3) — post-1.9 hot windows only.
---

# VRE ACC Tyres

ACC **1.9+** tyre model. Cold garage psi is a starting point; **hot stint telemetry** is the truth.

## Sources

- `ac_app/config/acc/gt3_physics_kb.json` — `tyre_dry_hot_pressure`, `tyre_wet_hot_pressure`, `tyre_temp_window`
- `ac_app/config/acc/cars/ferrari_296_gt3.json` — `tyre_traits` (296: slow front heat, front inside grain when cold/over-steered)
- `ac_app/config/acc/kb_loader.py` — loaders; **`reject_pre_19_advice()`** on any cited forum numbers

**Version pin:** `verified_on` **1.10.3**, `acc_min_version` **1.9.0**. Do not primary-coach from pre-1.9 pressure spreadsheets.

## Targets (dry slick, hot)

| Signal | Window |
|--------|--------|
| Hot pressure | **26.0–27.0 psi** (`tyre_pressure_windows_psi.dry_hot`) |
| Core temp | **70–100 °C** |
| Wet hot | **30–31 psi** |

## Symptom → first levers (pace-first)

| Symptom | Try first | Not first |
|---------|-----------|-----------|
| `front_grain` + under-temp | Raise front hot pressure toward window, shorten cold abuse, brake duct / stint pace to build heat | Random damper softening |
| `low_front_hot_psi` | `PRESSURE_FRONT` (cold adjustment validated on hot trace) | Camber-only without pressure proof |
| `slow_front_heat` | Driving: longer brake zones into heat; ducts; one pressure step — **296 note** in car profile | Rear wing or diff to “fix” front feel |

```bash
python -m external.query_tools.acc_ingest.setup_hints --symptom front_grain --car ferrari_296_gt3
```

## A/B protocol

≥ 5 clean flying laps per variant, tyres in window, skip out-laps. Compare:

```bash
python external/query_tools/driver_lab.py compare -a <session>:<laps A> -b <session>:<laps B>
```

Verdict: faster median or equal pace with even temps across stint — not “less grain but slower.”

**REQUIRED SUB-SKILL:** `vre-acc-setup` for non-tyre levers; `vre-teach-answer` for the driver-facing answer.