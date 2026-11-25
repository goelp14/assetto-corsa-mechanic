---
name: vre-explain-dynamics
description: Use when the user asks why something happened mechanically — understeer, oversteer, grip, tyres, load transfer, elevation.
---

# VRE Explain Dynamics

**Scope: Cross-game physics (universal; magnitudes are car-specific — see `vre-car-research`).**

Ground mechanism explanations in evidence + glossary.

## Rules

1. Start from a metric in the evidence pack or a `driver_lab.py` output — never parametric-only physics
2. Link metric → mechanism → driver action
3. Read [dynamics-glossary.md](../../docs/coach/dynamics-glossary.md) for vocabulary and the proven chains, and
   [car-handling-theory.md](../../docs/coach/car-handling-theory.md) for the handling model (rotation, three tools for
   rotation, weight-transfer levels, correction priority, elevation/camber, V vs U by downforce)

## Common chains

| Observation | Mechanism | Fix |
|-------------|-----------|-----|
| Off both pedals while turning, understeer rising | No axle loaded → front unloaded, car stops rotating | Overlap brake release into throttle pickup |
| Brake fully released at turn-in, rear slides in 1st/2nd gear | Engine braking on the rear only | Progressive release; trail to the apex; don't coast in low gears |
| Heavy trail (> 60%) at turn-in, inside front lock | Unloaded inside front over-braked | Brake hard straight, ≤ 1/3 pedal by turn-in; or bias rearward |
| Braking zone over a crest | Vertical load drops (up to −80%) → brakes lock / car floats | Brake before the crest, light over it, reapply after landing |
| Compression on exit or in a braking zone | Extra vertical load (+20–60%) | Commit throttle / brake harder there |
| High throttle + high lateral load | Rear overloaded while turning | Unwind first, then commit quickly |
| Re-steer after the apex at steady throttle, no slip | Car not pointed (line/rotation), not grip | Fix entry rotation; later apex |
| `susp_ratio` in kerb band | Tyre unloaded | Avoid kerb or pause inputs |
| `delta_us` positive | Understeer | Keep front loaded (trail), reduce entry speed |
| `delta_us` negative | Oversteer | Smooth throttle, reduce steer rate |

## Evidence fields

`beta_deg`, `delta_us_deg`, `yaw_rate`, `heading`, `wheel_load[4]`, `wheel_slip`, `wheel_rads` + `tyre_radius_m`
(long-slip = 1 − ωr/v; peak grip ≈ 8–10%), `throttle`, `brake`, `steer_deg`, `susp_ratio`, `pos_x/pos_z`.

Don't use raw `acc_g_lat` as a grip ceiling — kerbs and compressions inflate it past 2 g on a no-aero car; use v²·κ from
the driven path (`driver_lab.py sim` prints per-corner values).

**REQUIRED SUB-SKILL:** Use `vre-teach-answer`

## Measured mechanisms (replays, any car)

`external/query_tools/coach/physics.py` turns measured car state into mechanisms — use these instead of generic claims:

- `crest_effect(expected_dg)` — load change over a crest/dip from track curvature × speed² (`pack.terrain[].dg_at_100kmh`
  scales with (v/100)²). Crest = light car: finish braking before it. Dip = loaded car: a place to brake, turn or apply power.
- `braking_balance_check` — braking slip front share vs **0.5** (equal slip = both axles near peak; the force split then
  follows the dynamic load split by itself). Not vs the load share.
- `load_transfer(car_state, lat_g)`, `aero_at(car_state, speed)` — measured lateral transfer split and downforce.
- `MECHANISM` — direction + why for each setup lever; magnitudes only from per-car calibration (`vre-car-research`).
