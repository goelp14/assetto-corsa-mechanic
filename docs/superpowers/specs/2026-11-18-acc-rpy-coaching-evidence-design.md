# ACC `.rpy` coaching evidence + Motec analysis export

**Status:** design approved (user 2026-11-18)  
**Scope:** A (replay-alone coaching extract) + C (skills) + Motec `.ld` analysis overlay file  
**Out of scope:** inventing physics; calming-only setup; citing unlocked/guessed channels as facts

## Problem

Coaching (pace, coast/pedal gaps, TC/ABS, corner compare, setup/damper advice) needs exact telemetry, lap validity, and environment. Today:

- MoTeC/SHM can supply that for the driver’s own sessions.
- Foreign `.rpy` (e.g. faster reference) only reliably yields structure, pose, and (newly) lap times from the current-lap timer stream.
- Agents still invent spline phase / valley labels when Motec alignment is hard.
- There is no Motec-openable artifact that shows VRE analysis math next to raw channels.

## Goal

From any ACC `.rpy` (and optionally a same-stint MoTeC `.ld`), produce:

1. A **coaching evidence pack** with only GO fields (exact laps, validity, env, ≥20 Hz driving channels when unlocked).
2. A **Motec `.ld`** the user can open in i2 with raw telemetry + VRE analysis channels overlaid.
3. **Skills** so future agents gather and cite that pack instead of re-guessing.

Reusable for any GT3 car/track: wire extract is car-agnostic; track geometry/corners from `ac_app/config/tracks/<track>_acc.json`; car setup doctrine from `gt3_physics_kb` + `cars/<car>.json`.

## Evidence contract (no guessing)

A coaching claim may cite only:

| Source | Allowed when |
|--------|----------------|
| MoTeC / SHM samples | Always (native channel rates; never truncate all series to shortest length) |
| `.rpy` field | Documented Motec/SHM agreement in `docs/superpowers/specs/` (tolerance + fixture pair) |
| Explicit hypothesis | Labeled “hypothesis — not GO”; never used as setup proof |

**Already GO**

- Lap times from current-lap timer stream (u32 ms, stride 24, S/F reset) via `extract_lap_times_ms` — Spa gold vs MoTeC `TIME` resets Δ ≤ 7 ms.

**Not GO until locked**

- Speed / throttle / brake / steer / gear / TC / ABS from `.rpy` arrays.
- Pose-derived speed as a substitute for pedal coaching or setup advice.
- Inferred corner IDs from “valley detection” without a locked distance/spline or Motec lap.

## Architecture

```text
.rpy ──► structural processor ──► arrays + pose + weather blobs
              │
              ├─► extract_lap_times_ms          (GO)
              ├─► validity decoder              (to unlock)
              ├─► env decoder (weather/grip)    (to unlock)
              └─► Motec-lock channel map        (to unlock GO)
                        │
MoTeC .ld ──────────────┴─► normalize / gold tests
                        │
                        ▼
              coaching evidence pack
                        │
                        ├─► VRE session / exports (driver_lab, coach)
                        └─► vre_analysis_<session>.ld  (Motec i2)
```

### Extract pipeline (`external/query_tools/acc_rpy/`)

1. **Structural walk** — existing `processor.py` (header, weather, cars, snapshots, `rec_68`, bulk arrays).
2. **Lap times** — `parse_rpy.extract_lap_times_ms` (done).
3. **Validity** — find per-lap / per-frame valid flag corresponding to SHM `graphics.isValidLap`. Search order: leaderboard section, driverInfo `0x30`/`0x20` records, timer-stream companion fields, snapshot array columns. Gold: sessions with known cuts/invalids.
4. **Environment** — map `weatherData` 7×f32 + related status fields to SHM-like names (`trackGripStatus`, rain intensity, ambient). Document units after Motec/SHM cross-check where possible; otherwise expose raw floats as `RPY_WEATHER_*` until mapped.
5. **Driving + platform channels** — Motec-lock SPEED, THROTTLE, BRAKE, STEER, GEAR, G_LAT/G_LON, ROTY/yaw, suspension travel (and TC/ABS) from rpy arrays where possible; when the user’s own MoTeC `.ld` exists, **ingest the full Epic channel set** (see Motec section) rather than a stripped subset. Flip `RPY_TELEMETRY_GO` only when gold fixtures pass documented thresholds.
6. **Emit** — `sessions_acc/` and/or `exports/<id>/` with `rpy_telemetry_go` reflecting real gate status; always offer Motec analysis `.ld` when enough GO channels exist for a useful overlay.

### Motec analysis `.ld` writer

**Path:** e.g. `external/query_tools/acc_ingest/motec_analysis_ld.py` (or `acc_rpy/write_analysis_ld.py`).

**Input:** full ACC MoTeC channel set (when `.ld` is available) and/or GO rpy + SHM-enriched samples + analysis pack.

**Output:** `vre_analysis_<session_id>.ld` openable in Motec i2 (use with Kunos `base_ACC` workspace worksheets where possible).

#### What ACC MoTeC already exports (Spa gold inventory)

Preserve these in the analysis `.ld` (native rates — do not downsample to one rate):

| Group | Channels | Setup / coaching use |
|-------|----------|----------------------|
| Driver | SPEED, THROTTLE, BRAKE, STEERANGLE, GEAR, RPMS, CLUTCH | Compare / Driver worksheets; coast & throttle-ramp |
| Platform | G_LAT, G_LON, **ROTY** (rad/s yaw rate) | Balance, rotation, US/OS maths |
| Suspension | SUS_TRAVEL_*, BUMPSTOP*, WHEEL_SPEED_* @ 200 Hz | Travel, pitch/rake proxy, damper velocity histograms, lock/spin |
| Tyres / brakes | TYRE_PRESS_*, TYRE_TAIR_*, BRAKE_TEMP_* | Pressure window, thermal, brake duct |
| Electronics | TC, ABS | Intervention vs exit confidence |
| Session | TIME (lap-local resets), LAP_BEACON (often empty in ACC — prefer TIME) | Exact laps |
| Opaque EN_* | EN_AP, EN_Dy, EN_ET, EN_GR, EN_TB, EN_TD, EN_TL, EN_TW, EN_W | **Do not invent meanings** until Motec workspace / Kunos docs / SHM correlation names them; pass through as raw |

SHM can add (when logging live, not from stock Epic `.ld`): **pitch**, **roll**, slipAngle/slipRatio, rideHeight, wheelLoad, surfaceGrip, airTemp/roadTemp, `isValidLap`, trackGripStatus, rain*. Prefer these for rake/pitch and grip when present.

#### Useful Motec workflows (research → product)

Align VRE math + exported channels with what engineers actually use in ACC Motec ([Kunos workspace](https://www.acc-wiki.info/wiki/MoTeC_Support), [Coach Dave](https://coachdaveacademy.com/tutorials/how-to-use-motec-data-in-assetto-corsa-competizione/), [SOLOX](https://solox.gg/acc-motec-guide/), [Trinacria](https://trinacriasimracing.wordpress.com/basic-use-of-telemetry-for-spring-damper-assembly-setup/)):

| Worksheet / technique | Channels / maths | Setup lever (pace-first) |
|----------------------|------------------|---------------------------|
| Compare / Driver | speed, pedals, steer, G | Driving first; only then setup |
| Wheelspeed | WHEEL_SPEED_* vs SPEED; TC/ABS | TC1/TC2, ABS, diff exit, brake bias |
| Understeer / Oversteer | Motec math from SPEED, STEERANGLE, G_LAT, throttle, brake (+ Oversteer math channel in ACC workspace) | Springs/ARB/aero/diff **after** confirming the pattern is multi-corner, not one mistake |
| Suspension histogram | d(SUS_TRAVEL)/dt → damper velocity; bell shape low-speed bump/rebound | Slow bump/rebound clicks; last 1% after balance |
| Suspension travel / pitch | SUS_TRAVEL F vs R → rake/pitch under brake & power | Bumpstop range/rate, ride height, springs (platform for aero) |
| Yaw / rotation | ROTY, steer, G_LAT | Entry rotation vs push; trail-brake / rear ARB / diff entry |
| Tyre pressures/temps | TYRE_PRESS_*, TYRE_TAIR_* | Cold pressures into 26–27 psi hot dry window |
| Channel / section report | per-corner min speed, G, steer | Rank corners for time loss |

**Doctrine:** same as VRE ACC setup — driving consistency before dampers; dampers after springs/ARB; never “calmer but slower.”

#### Channel groups in `vre_analysis_*.ld`

1. **Raw ACC** — full preserved Motec set above (plus SHM extras when available).
2. **Session** — TIME, synthetic LAP_BEACON from TIME resets, LAP_DIST/spline, **VALID_LAP**.
3. **Derived platform (GO when inputs GO)**  
   - `VRE_DAMPER_VEL_*` from SUS_TRAVEL derivative  
   - `VRE_RAKE_PROXY` / `VRE_PITCH_PROXY` from F−R travel (or SHM pitch)  
   - `VRE_YAW_RATE_DEG` from ROTY  
   - `VRE_US_OS` — documented Motec-style balance math (steer vs expected from speed×G); require steering-lock constant from car profile (296: 400°)  
   - `VRE_WHEELSPIN` / `VRE_LOCK` from wheel vs ground speed  
4. **VRE coaching** — `VRE_COAST`, `VRE_PEDAL_GAP`, `VRE_TC_ACTIVE`, `VRE_CORNER_ID`, `VRE_DELTA_TO_REF_*`, `VRE_REF_SPEED`.
5. **Env** — grip/rain/ambient when decoded (`VRE_TRACK_GRIP`, …).

**Rules**

- Do not write analysis channels derived from non-GO rpy fields.
- Do not label EN_* until correlated; still include them in the file for Motec worksheet compatibility.
- Dual-driver compare: align on distance/spline; delta channels explicit.
- Companion CSV optional (corner table / lap list / setup hint candidates) beside the `.ld`.

### Any car / track

| Layer | Responsibility |
|-------|----------------|
| `.rpy` wire | Car-agnostic Kunos layout (version-gated) |
| Track config | `ac_app/config/tracks/<track>_acc.json` — length, corners, sectors |
| Car doctrine | `gt3_physics_kb.json` + `cars/<car_id>.json` |
| Fixture gate | ≥1 MoTeC+`.rpy` pair before marking that track’s helpers GO |

### Skills (C)

1. **`acc-rpy-re`** (expand) — evidence contract; lap-timer method; validity/env search procedure; Motec-lock checklist; refuse coaching from unlocked channels; Motec analysis `.ld` as deliverable when user asks to “see analysis in Motec”.
2. **`vre-coach-router` / `vre-collect-evidence`** — ACC path: prefer MoTeC/SHM; if only `.rpy`, require GO fields or limit claims; never invent valley/spline timing when Motec exists.
3. **`vre-acc-setup` / `vre-dampers`** — cite Motec worksheet equivalents (US/OS math, suspension histogram, travel/pitch, wheelspeed) and map to ACC levers; require multi-corner pattern + `compare` before setup change.
4. **Coaching citation section** — which VRE skills may cite which Motec/rpy channels (raw vs derived).

## Success bar

- Erik `.rpy` alone → best **valid** flying lap ~2:15.x, env stated if GO, corner compare from locked channels (or explicit NO-GO).
- Spa gold → rpy laps/channels agree with MoTeC within documented tolerances.
- User opens `vre_analysis_*.ld` in Motec and sees raw ACC channels (incl. ROTY, SUS_TRAVEL, tyre P/T) + VRE_* overlays (coast, US/OS, damper vel, delta-to-ref) for analyzed laps.
- Setup advice can point at the same Motec traces the user is viewing (e.g. “rear histogram soft → rebound +2”) with GO evidence.
- Agent with updated skills does not invent spline phase, EN_* meanings, or treat pose speed as pedal data.

## Implementation order (high level)

1. Spec + plan (this doc → `docs/superpowers/plans/…`).
2. Validity + env RE (Ghidra + gold) with tests.
3. Channel Motec-lock iteration until GO or documented blockers.
4. Motec analysis `.ld` writer + fixture test (round-trip discover channels).
5. Skill updates + a short pressure check that agents refuse unlocked claims.
6. Re-run Tomato vs Erik coaching using only GO evidence + ship `.ld`.

## References

- `docs/superpowers/specs/acc-rpy-wire-from-exe.md`
- `external/query_tools/acc_rpy/parse_rpy.py` (`extract_lap_times_ms`)
- `external/query_tools/acc_ingest/motec_ld.py` (TIME-reset lap splits)
- `external/query_tools/acc_ingest/shm_structs.py` (`isValidLap`, weather/grip fields)
- Skills: `acc-rpy-re`, `vre-coach-router`, `vre-collect-evidence`, `vre-acc-setup`
