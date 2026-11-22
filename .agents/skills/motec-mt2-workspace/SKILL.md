---
name: motec-mt2-workspace
description: Use when Motec Track Map shows labels only / blank stroke, "No distance calculated", Corr Dist missing, .mt2 section renames, Internal Maths / CircuitMaths SPEED, or verifying rpy lap times against Motec .ldx — never guess times or regenerate maps blindly.
---

# Motec .mt2 + workspace (evidence-gated)

## Overview

Track Map stroke needs **Corr Dist** from CircuitMaths resolving channel **SPEED**.
Lap times come from **rpy valid flying laps** vs **.ldx BCN gaps** — never eyeball.

## Evidence (do not rediscover)

| Source | Fact |
|--------|------|
| [Motec forum t=4926](https://forum.motec.com.au/viewtopic.php?f=26&t=4926) | Track cursor = beacon + Corr Dist (not GPS). Speed channel priority list; wheel FL/FR steals priority if present. |
| [i2 Training Seminar 2008](http://www.precisionautoresearch.com/DOWNLOADS/Motec%20Interpreter/i2%20Training%20Seminar%202008.pdf) pp.37–39 | Track map needs lateral G + vehicle speed + beacon. Distance mode needs Corr Dist. |
| ACC Workspace V1 `Internal Maths.xml` | `Params="4:0;…:1:[SPEED;Ground Speed;…]"` — SPEED first, dual-wheel OFF. |
| Broken Motec default | `4:1;…:[Ground Speed;Wheel Speed…]` — no SPEED → blank stroke. |
| OverTake Spa .mt2 | Community maps exist; rename `.txt`→`.mt2`, copy into project Track Maps. Prefer ACC_NN / `track_pack/mt2/Spa.mt2`. |
| This repo | Same-length UTF-16 renames only (`mt2_sections.py`). Size change → labels without polyline. |

## MUST before claiming Motec is good

```bash
cd .
PYTHONPATH=. python3 -m external.query_tools.acc_rpy.verify_motec_export \
  --motec-dir exports/spa_pace_tomato_erik_20261119/motec \
  --driver 'fixtures/Tomato.rpy:exports/.../Tomato.ld:Tomato' \
  --mt2-source external/query_tools/acc_rpy/track_pack/mt2/Spa.mt2
```

Pass criteria:
1. Every **valid flying** rpy lap_ms matches an .ldx BCN gap within **50 ms**
2. .ldx Details `Fastest Time` == best valid flyer (e.g. Tomato `2:19.072`, Erik `2:15.425`)
3. `Internal Maths.xml` CircuitMaths list contains **SPEED**; dual-wheel pair `4:0`
4. Venue `.mt2` has MoTeCTrackV2 + Points/Data + SectionGroups; **byte size == pristine**
5. `.ld` has SPEED + G_LAT with real samples

## Generate / repair checklist

1. `write_motec_workspace_bundle` — ships `ACC_INTERNAL_MATHS_XML` + SPEED `Overrides` DisplayUnit=km/h
2. `install_acc_track_maps` — copy ACC_NN / `track_pack/mt2`, then `patch_mt2_from_track_config` (same-length names)
3. Open via `Open_VRE.ps1` only (gates SPEED in Internal Maths after robocopy)
4. In Motec: Track Map sheet active; F9 for distance; confirm Corr Dist increments with speed
5. If stroke still blank: Tools → Corrected Speed and Distance — ensure SPEED ticked; regenerate only if no venue .mt2 (`Tools → Track Editor → Generate Track` on a flying lap)

## Two drivers (Main + Ref) — proven 2026-11-19

- Registry `HKCU\Software\MoTeC\i2\1.1\LoadPrevData=1` + launch `i2 -w <ws>` (no `-l`).
  `LoadPrevData=0` (Motec default) → `-w` opens zero logs; `-l X.ld` replaces
  DataSources with X only (Ref lost); a 2nd `i2 -l` spawns a new instance.
- Motec numbers `[log start, first BCN]` as Lap 1. Never write a BCN at t=0
  (empty Lap 1 shifts every label +1 → wrong Main/Ref lap).
- `.ld` freq is an integer: resample channels onto `arange(0, span, 1/hz)`
  (`resample_uniform`). Tomato 11.28 Hz written as 11 Hz drifted beacons off S/F.
  Check: SPEED at every BCN ≈ same value (Spa ≈ 163–169 km/h after Bus Stop).
- Venue must match the `.mt2` basename for both logs (ACCReplay `…_Q_Spa_ERIK`
  parses Spa as *car* — venue lookup also reads filename `stem`).
- Stair-step traces when zoomed = Motec sample-and-hold on native 8–11 Hz inputs.
  Export grid is `MOTEC_EXPORT_HZ` (50; env `VRE_MOTEC_HZ`) with linear interp,
  step-hold for gear/flag/map. Display smoothing only — ACC records no more.
- Verify picks `<.ld Venue>.mt2` automatically (case-insensitive; Monza ships
  `monza.mt2`). No venue map → warning, not failure. `--workspace` accepts a full path.
- Track-map SPEED contour is km/h (40–280, `_speed_bands_xml`); the ACC preset's
  0–80 bands are m/s and paint a whole GT3 lap red once SPEED displays km/h.
- Generality proven: Spa pair, Monza single, Imola pair all pass verify + open in Motec.

## BAN

- Guessing lap times from Motec UI without rpy `lap_validity` / `.vre_fastest_time`
- Rewriting .mt2 UTF-16 Name **lengths** (breaks Points/Data alignment)
- Blind Motec channel sweeps for pedals (see pedal-unlock playbook)
- Trusting Documents `VRE_Export/Internal Maths.xml` if export source lacked the file (robocopy won't delete stale Motec default)

## Tools

| Tool | Path |
|------|------|
| Verify gate | `external/query_tools/acc_rpy/verify_motec_export.py` |
| Workspace writer | `external/query_tools/acc_rpy/motec_workspace.py` |
| Size-safe .mt2 labels | `external/query_tools/acc_rpy/mt2_sections.py` |
| Pristine Spa map | `external/query_tools/acc_rpy/track_pack/mt2/Spa.mt2` |

## VRE pose channels (vre-rpy export v2, ACC)

Exports add, beside the native lanes: `GPS_LAT/LONG` from pose, wrap-safe `LAP_DIST`, `VRE_BETA_DEG` (body slip),
`VRE_YAW_RATE`, `VRE_UNDERSTEER_DEG` (steering ratio assumed 11:1 — compare, don't read absolutely), `VRE_ELEV/GRADE/VERT_CURV`
(terrain), `VRE_EDGE_ALL4/ANY_L/R_M` and `VRE_LAT_OFFSET_M` (line + limits), `VRE_CORNER_ID`, `VRE_VALID`, `VRE_CUT_JUDGED`,
`VRE_PRED_LAP_S/DELTA_S`, `VRE_SYNC_OK` (only trust laps where it is 1), `VRE_LOAD_TOTAL`, `VRE_TC_EST`/`VRE_ABS_EST`
(slip-based estimates, not the game's flags). Worksheets: **VRE Corner**, **VRE Terrain**, **VRE Limits**.
`vre-rpy verify` checks all-zero channels, LAP_DIST resets and GPS vs LAP_DIST scale.
