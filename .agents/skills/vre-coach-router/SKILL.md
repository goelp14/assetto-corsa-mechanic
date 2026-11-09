---
name: vre-coach-router
description: Use when the user asks about lap telemetry, spins, corner technique, lines, setup, controls, pace potential, driving style, stint debrief, or why something happened on track.
---

# VRE Coach Router

Entry point for every driver-coaching question. Pick the route, gather evidence, find the root cause, then answer.

## Ground rules (learned the hard way)

1. **Root cause before advice.** "Throttle earlier", "stop coasting", "brake later" are symptoms. Trace upstream
   (entry → rotation → line → throttle) before prescribing. The driver will push back on symptom-level advice, and be right.
2. **Controls before technique.** If inputs feel "not registered" or light trail-braking seems absent in data,
   run `driver_lab.py controls` first. A brake GAMMA of 2.4 (20% pedal → 2% brake) explained a full day of "coasting".
3. **Test claims on the driver's own passes.** Compare fastest vs slowest quarter of passes through the same corner and
   correlate with section time. A claim the data can't separate (|r| < ~0.35, or outside the driver's tried range) is a
   hypothesis to test on track, not advice.
4. **Never extrapolate outside the tried range.** If every pass entered within ±1.8 m, the data cannot say whether 3 m wider
   is better — propose a 5-lap test instead.
5. **Corners are coupled.** Check the next corner before praising a faster exit/min speed: T3→T3a and T8→T8a traded time
   (r ≈ −0.4…−0.6). Treat complexes as one corner.
6. **Visual cues, not metres.** Drivers have no distance boards. Translate every point into a landmark
   (`objs_on_track.json`-style object scan, kerbs, pit-lane split, crests) and say when a cue is unverified.
7. **Pace first, always.** Never recommend a setup or technique change because it makes the car calmer; only because it
   makes the driver faster (or equally fast and more confident). "More stable but slower" is a failed change.
8. **Fit the driver, not a template.** Read the driver profile before setup or style advice; extend their natural style.

## Any car, any track

- Track config missing? Generate it: `python tools/build_track_config.py <track> --layout <layout>` (corner names via
  `--names`), then check corner directions against steering — `driver_lab` uses steering sign, not config `direction`.
- Car setup ranges/units: `python tools/extract_car_profile.py` → `ac_app/config/cars/<car>.json`.
- Example numbers in these skills come from one car/track (312/67, Sonoma Long). Re-measure; keep the methods.

## Data sources

| Source | When | Tool |
|--------|------|------|
| Live/archived session dirs (`.../VirtualRaceEngineer/data/sessions/<id>/laps/lap_NN.json`) | Live coaching, root cause, lines, sim | `python external/query_tools/driver_lab.py <cmd> -s <session> ...` |
| Replay bundles (`exports/<session_id>/`) | Replay viewer questions, citations | `python -m external.query_tools.coach pack/ask` |
| AC `controls.ini` | Input feel, "miscalibration" | `driver_lab.py controls` |
| Driver profile (`ac_app/data/driver_profile.json`) | Style, preferences, setup fit, trends | `driver_lab.py style` |
| Setup A/B | Any setup or controls change | `driver_lab.py compare -a ... -b ...` |
| Car `data.acd` / setup `.ini` | Setup ranges and units | `tools/extract_car_profile.py` |

Always pass `--min-lap/--max-lap` to drop spins, offs and out-laps, and group laps by setup/controls change
(a gamma or brake-bias change mid-session splits the data into different cars).

## Route by intent

| Intent | Sub-skill |
|--------|-----------|
| spin, crash, snap, lost control | `vre-incident-analysis` |
| "why am I slow at X", exits, hesitation, coasting, "one corner better → next worse" | `vre-root-cause` |
| line, apex, turn-in point, "should I be more left/right" | `vre-line-analysis` |
| technique drill for one corner, braking point, visual cues | `vre-corner-coaching` |
| understeer/oversteer/grip mechanism | `vre-explain-dynamics` |
| setup change, brake bias, diff, ARB, "feels wrong", input calibration | `vre-setup-and-controls` |
| "how fast could I be", alien gap, driver comparisons | `vre-pace-potential` |
| "what's my style", style trend, end of session | `vre-driver-profile` |
| driver is on track and laps are arriving | `vre-live-session` |

Most real questions chain: e.g. slow exit → `vre-root-cause` → `vre-line-analysis` (entry position) → `vre-corner-coaching` (cues).
Setup questions always chain: `vre-setup-and-controls` (controls check) → `vre-root-cause` (is it technique?) →
`vre-driver-profile` (style fit) → one lever → `driver_lab.py compare` verdict.

**REQUIRED SUB-SKILL:** `vre-collect-evidence` (bundle questions) or the `driver_lab.py` commands named in the sub-skill.

**REQUIRED SUB-SKILL:** `vre-teach-answer` for the final response.

After lap/corner-specific coaching on a replay bundle: **REQUIRED SUB-SKILL:** `vre-annotate-replay`.

## Bundle CLI

```bash
python -m external.query_tools.coach ask --bundle exports/<session_id> --question "<q>" --corner <id> --lap <n>
```

Read [CONTEXT.md](../../CONTEXT.md) for domain terms and [dynamics-glossary.md](../../docs/coach/dynamics-glossary.md) for proven cause chains.
