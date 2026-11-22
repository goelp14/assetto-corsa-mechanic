---
name: vre-car-research
description: Use when advice depends on a specific car (setup ranges, click units, brake-bias offsets, engine/gearing, TC/ABS behaviour, aero sensitivity, known handling traits) in AC or ACC, or when a car has no profile yet.
---

# VRE Car Research

**Scope: cross-game procedure; AC and ACC store results in different places.**

## Universal vs car-specific

| Universal (state freely, any car, both games) | Car-specific (must be researched or measured) |
|---|---|
| load transfer, friction circle, slip angle/ratio, aero ∝ v², crest/dip load change | setup click ranges and units, brake-bias offset per car (ACC shows % that is not the true split) |
| peak brake pressure early, bleed as speed falls; minimum speed + exit decide time | engine power band / shift points, gear ratios, final drive |
| stiffer front bar → more front load transfer → more understeer (direction) | how much one click changes anything (magnitude) |
| tyres work in a pressure/temperature window | the window's numbers (ACC GT3 dry hot ≈ 26–27 psi post-1.9; AC per car/tyre) |
| TC/ABS trade slip for stability | TC/ABS map behaviour and cut levels per car |

Never present a car-specific magnitude as universal. Directions + mechanism are fine without research.

## Research order (stop when two independent sources agree)

1. **Measure first** — it beats any forum: `vre-rpy setup FILE` (exact gearing per gear, tyre radii, mass, weight split;
   estimated aero/braking/roll signatures), `analysis.car_state` (understeer gradient, load transfer split, downforce at 200 km/h).
   AC: `python tools/extract_car_profile.py` reads `data.acd` → exact ranges/units.
2. **Game files / official** — ACC: Kunos patch notes and the car's BoP for the game version (filter pre-1.9 advice with
   `reject_pre_19_advice`). AC: the car's `data` folder.
3. **Setup files from fast drivers** for that car + track (the user's library: `VRE_ACC_SETUPS`, or public collections such as
   `github.com/Lon3035/ACC_Setups`). Read *differences between* setups, not one setup's numbers.
4. **Coaching sites** (Coach Dave Academy, Track Titan, HPAcademy, Driver61) for traits and technique; real-world manufacturer
   material for the real car's character. Treat as hypotheses until the data agrees.

Cite every source in the answer and mark anything not cross-checked as unverified.

## Where to store it

- ACC: `ac_app/config/acc/cars/<car_id>.json` (traits, electronics bands, steering lock, verified_on version) and
  levers in `ac_app/config/acc/gt3_physics_kb.json`. Car ids: `vre_rpy.ids.CAR_MODELS`.
- AC: `ac_app/config/cars/<car>.json` via `tools/extract_car_profile.py`.
- Per-car **sensitivities** (what one click did, measured with A-B-A runs) go into the driver profile calibration — that is the
  only legitimate source of magnitudes in setup advice.

## Don't overfit

One car's numbers never become defaults for another. Examples in skills (Ferrari 296 GT3, Sonoma 312/67) are examples:
re-measure on the current car and keep only the method.
