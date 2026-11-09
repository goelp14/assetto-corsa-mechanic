# Dynamics Glossary (VRE metrics)

Curated reference for the telemetry coach agent. Link evidence to these concepts — do not invent numbers.

## Slip and yaw

| Metric | Field | Meaning |
|--------|-------|---------|
| **Beta (β)** | `beta_deg` | Body slip angle — rear stepped out vs velocity vector |
| **Yaw rate** | `yaw_rate` | Rotation rate; spikes precede spins |
| **Delta US** | `delta_us_deg` | Understeer gradient — positive = understeer, negative = oversteer |

**Loss of control:** `beta_deg` > 35° (terminal) or counter-steer with growing yaw error.

## Load and grip

| Metric | Field | Meaning |
|--------|-------|---------|
| **Lateral G** | `acc_g_lat` | Cornering load — tyre lateral force proxy |
| **Longitudinal G** | `acc_g_long` | Braking/acceleration load |
| **Susp ratio** | `susp_ratio[4]` | Per-wheel suspension compression — kerb/bump detection |
| **Wheel load** | `wheel_load[4]` | Per-corner vertical load |

**Throttle under lateral:** Power while `acc_g_lat` > 0.6G shifts load rearward → rear slip.

## Inputs

| Metric | Field | Coaching cue |
|--------|-------|--------------|
| **Throttle** | `throttle` 0–1 | Wait until G falls before power |
| **Brake** | `brake` 0–1 | Trail release shape matters |
| **Steer** | `steer_deg` | One smooth trace — corrections = fighting grip |

## Surface events

| Symptom | Evidence | Mechanism |
|---------|----------|-----------|
| Kerb unload | `susp_ratio` in painted kerb band | Inside tyre unloads → grip loss |
| Platform hop | High vertical G + yaw err | Car unsettled mid-corner |
| Scrub | High mid-corner speed vs reference | Tyres sliding, not rotating |

## Proven cause chains (validated on driver laps)

Correlations from 22 passes per corner, Ferrari 312/67 at Sonoma Long (`driver_lab.py corner|coast`). Treat as priors
to re-test on other cars/tracks, not constants.

| Chain | Evidence |
|-------|----------|
| Brake GAMMA 2.4 → light trail braking disappears → coasting, rear slides, stability-biased setups | gamma 1.0: slides 2.1 → 0.5/lap, coast 13 → 8 s/lap |
| Brake-off → throttle gap in a hairpin → more lock at apex → post-apex re-steer → low exit speed | r(gap, lock) +0.61; r(re-steer, time) +0.67 |
| Rear rotation on entry → less lock needed | r(rear slide, lock) −0.64; fastest pass ~15° slide |
| Brake released at turn-in of a long corner → nose unloaded → understeer drift to outside → lifts on exit | later release −2° lock, −0.1 s; lifts r +0.55 with time |
| Early/tight turn-in → wide mid-corner → part throttle | slow passes both slower and wider (T2, T7) |
| Braking over a crest → brake-coast-brake pattern | Carousel crest −79% load at the brake zone |
| Faster exit of corner N → worse corner N+1 in complexes | T3→T3a r −0.57, T8→T8a r −0.41 |

Coast classification (`driver_lab.py coast`): A rear stepping out, B front not turning, C brake-release gap, D throttle lift.
Only A is a stability save; B and C are rotation problems.

## Measurement cautions

- `acc_g_lat` overshoots on kerbs/compressions; use v²·κ of the driven path for grip.
- `fast_lane.ai` side widths are approximate and left/right labels may be flipped; prefer edge-independent lateral offsets.
- Samples ≈ 9 Hz: aggregate over 10–20 m stations.
- Track-config corner `direction` can be wrong; derive from steering sign.

## Measurement caveats

- `acc_g_lat` is inflated by kerbs and compressions; use v²·κ of the driven path for grip (`driver_lab.py sim`).
- Long-slip = 1 − ωr/v with `tyre_radius_m`; peak grip around 8–10%; > 20% under brake = lock.
- AC pedal output = pedal^GAMMA from `controls.ini`; non-linear curves hide light inputs.
- `fast_lane.ai` side widths/labels are rough; measure lines relative to the AI line, not to the edges.

## Proven cause chains (validated on driver data; re-measure per car)

| Chain | Evidence pattern |
|-------|------------------|
| Pedal gap → no axle loaded → car stops rotating → more lock → re-steer after apex → late, hesitant throttle | coast gap ↔ lock at apex (+), re-steer ↔ section time (+), exit speed (−) |
| Brake released at turn-in in a long corner → front unloaded → understeer → drifts to outside mid-corner → part throttle and lifts | coast mid-corner, understeer ~3°, lifts after apex ↔ time (+) |
| Early/tight turn-in → wide middle → waiting with lock | slow passes both slower and wider mid-corner |
| Over-slowing in a hairpin → more correction, not a better exit | min speed ↔ re-steer (−) |
| Braking over a crest → load loss → brake-coast-brake | crest zone overlaps release/re-apply on slow passes |
| Compression on exit → extra grip available | driver hesitates where the sim shows +20–60% load |
| Faster exit in corner N → worse corner N+1 | negative correlation of adjacent corner times |

## Setup doctrine

Pace first. Stability levers (forward bias, more diff coast/preload, softer rear bar, stiffer front bar, rear toe-in,
more rear wing) cost rotation; use them only with evidence that instability costs more time. Try grip levers
(pressures, camber, gearing, ride height, springs, aero balance) first. Judge with `driver_lab.py compare` (A-B-A, ≥ 5 laps).

## F1 / sim racing reading order

1. Where was time lost? → `time_loss.json`
2. Which phase? → speed + inputs for that spline range
3. Who got to power first? → throttle trace vs reference
4. One fix → drill from `session_plan.json`
