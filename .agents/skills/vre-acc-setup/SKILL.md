---
name: vre-acc-setup
description: Use for ACC GT3 garage setup (aero, springs/ARB, dampers, diff, brakes) when game is ACC or car is ferrari_296_gt3 — pace-first, post-1.9 physics only.
---

# VRE ACC Setup

**Assetto Corsa Competizione** GT3. Goal: **repeatable stint pace**, not a calmer car.

## Sources (read first)

| File | Use |
|------|-----|
| `docs/superpowers/specs/acc-motec-pace-setup.md` | Motec worksheets ↔ VRE channels ↔ levers; **Sonoma transfer** |
| `external/query_tools/acc_rpy/motec_worksheets.py` | Same map for agent packs (`motec_pace_setup.json`) |
| `ac_app/config/acc/gt3_physics_kb.json` | Lever → effect → when → telemetry (`verified_on` **1.10.3**, `acc_min_version` **1.9.0**) |
| `ac_app/config/acc/cars/ferrari_296_gt3.json` | Car traits, electronics bands, steering lock |
| `ac_app/config/acc/kb_loader.py` | `load_kb()`, `load_car_profile()`, `check_stale()`, **`reject_pre_19_advice()`** |
| `vre-setup-and-controls` / `vre-root-cause` | Sonoma 312/67: controls first, coast B+C ≠ soft car |

Filter any free-text advice through `reject_pre_19_advice`; reject legacy hot-pressure meta (~27.5–29 psi) without citing **26–27 psi** dry hot window.

## Doctrine

1. **Pace-first:** Accept a change only if median lap improves (or equal pace + better repeatability). "More stable but slower" ⇒ reject. Stability OK only when it **helps pace** or is pace-neutral but raises consistency.
2. **Never calm-only levers** (forward bias, soft ARB, high TC/ABS) without telemetry that instability costs lap time. Sonoma: calming the car lost time; gearing (pace lever) won.
3. **Motec worksheets before garage clicks:** Compare/Driver → Wheelspeed (spin/lock + TC/ABS **state**) → US/OS → Travel/Histogram → tyres. Cite worksheet + channel.
4. **Mechanical → aero → dampers → electronics** for balance; dampers on **1.10+** after springs/ARB are sane (`dampers_four_way` fact).
5. **Tyre window** before geometry chasing: dry hot **26–27 psi**, core **70–100 °C** (`tyre_dry_hot_pressure`, `tyre_temp_window`).
6. **Evidence:** setup claims need MoTeC/SHM (or GO rpy channels). Prefer `export_rpy_analysis` Motec overlays (`VRE_US_OS`, `VRE_COAST`, `VRE_TC_ACT`/`VRE_ABS_ACT`, `VRE_RAKE_LOAD`, `VRE_TRACK_GRIP`). Electronics: **levels** (`VRE_*_LEVEL`) ≠ **active** (`VRE_*_ACT`).

## Order of work

1. Confirm ACC build ≥ **1.9.0**; warn with `check_stale(installed, kb["verified_on"])` if older than KB.
2. **Controls / technique** (`vre-root-cause`, `vre-setup-and-controls` AC path) — ACC has no gamma.ini, but pedal habit still masks setup.
3. **Driver profile** (`vre-driver-profile`).
4. Symptom → hints: `python -m external.query_tools.acc_ingest.setup_hints --symptom <key> --car ferrari_296_gt3`
5. **A/B mandatory:** one lever per variant; **A-B-A** via `driver_lab.py compare` (ACC sessions under `data/sessions_acc/` once ingested).

```bash
python external/query_tools/driver_lab.py compare -a <session>:<laps A> -b <session>:<laps B> --max-lap <cut>
```

Reference vs personal: `external/query_tools.acc_ingest.ref_compare.summarize_lap_delta` for rough sector flags before naming a lever.

## Lever classes (ACC)

| Class | KB domain | Default stance |
|-------|-----------|----------------|
| Pace / grip | tyres, aero platform | Pressures into window, rake/ride height, camber for even temps |
| Rotation | springs_arb, differential | Rear ARB, diff entry/mid, brake bias rearward — when push costs time |
| Stability | brakes, diff | **Pace-costly**; evidence required |
| Transient | dampers | Kerbs/transitions after mechanical balance |

Chain: **tyre-specific** questions → `vre-acc-tyres`; **TC/ABS/ECU** → `vre-acc-electronics`.

**REQUIRED SUB-SKILL:** `vre-teach-answer` — one lever, class, telemetry check, compare verdict.