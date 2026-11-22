---
name: vre-acc-replay-analysis
description: Use when the user has ACC .rpy replays (their own and/or a faster driver's) and wants a lap comparison, corner breakdown, braking points, track limits, setup read-out or coaching from them — any car, any track.
---

# VRE ACC Replay Analysis

**Scope: ACC only** (the `.rpy` decoder). The analysis, coaching and video review downstream are cross-game.

## One command

```bash
./replay.sh --rpy "<my.rpy>:You" --ref "<faster.rpy>:Ref"      # builds exports/lab_<track>_You_vs_Ref_*/ and opens Lap Studio
python -m external.query_tools.acc_replay_bundle --rpy ... --ref ... --id NAME [--laps best] [--setups-dir DIR]
```

Needs `pip install -e <vre-rpy-cli>` (or `pip install -e .[acc]`). The public CLI is the source of truth for decoding:

| `vre-rpy` command | Gives |
|---|---|
| `cars FILE...` | cars in a replay (race/MP replays carry every car) → `--car-index` / `--ref-car-index` |
| `frames --rpy F[:Label] --out-dir D [--laps best\|all\|3,4]` | full-rate per-lap frames: true session time, metres from S/F, lateral offset, edge margins (all-4 / any wheel), XYZ, yaw/course/slip, inputs, G (incl. vertical), predicted lap, validity so far |
| `analyze --rpy ME --ref REF --out a.json` | corner windows (brake-to-brake, each contains its apex), events per lap, consistency vs section time, variance cliffs, theoretical best, car state |
| `limits --rpy F... --out l.json [--zone-model z.json]` | game verdict per lap + which excursion caused it (zone model, delayed verdicts), legal-track envelope |
| `setup --rpy ME [--ref REF] --out s.json [--setups-dir D]` | behaviour fingerprint (exact gearing/radii/mass; estimated aero, braking slip balance, roll share, diff, TC/ABS activity) + matching library setups |
| `track-pack [--track T] --out-dir D` | generated corners/terrain for any ACC track (+ curated names/notes layer) |
| `export --rpy F --out-dir D` / `verify --motec-dir D` | MoTeC .ld with VRE_* pose channels and worksheets, and its checks |

Then coaching: `python -m external.query_tools.coach.acc_coach --analysis analysis.json --setup setup.json --out coaching.json [--update-profile]`.

## What the replay can and cannot tell you (gates)

- **GO:** inputs (throttle, brake, steer, gear, rpm, speed), G lat/lon/vert, world velocity, pose (centre + 4 wheel contacts → yaw, slip angle, edge margins, elevation), tyre radii, per-wheel load & slip ratio (player car), lap times, sector splits, validity flag, ACC predicted lap.
- **Multi-car (race/MP) replays:** every car has pose + inputs; only the player car has per-wheel data. Pick a car with `--car-index` / `--ref-car-index` (`vre-rpy cars FILE`).
- **NO-GO:** the car setup (not in the file — the loader reads 100 % of it; use the fingerprint + library), tyre pressures/temps, suspension travel, TC/ABS "in action" (only slip-based estimates, labelled EST).
- **Sync gates:** pose and inputs run on separate clocks; the frames carry `sync.lap_r` and `lap_sync_go` (≥ 0.95). Laps failing the gate, partial laps and out-laps are excluded from analysis — say so if the user's lap is one of them.
- Native rates: pose ≈ 14–27 Hz, inputs ≈ 8–11 Hz → ±5 m on a braking point at 200 km/h. Never claim a 2 m difference as real.

## Method (pace first)

1. Read `coaching.json`: at most **two fixes**, each = belief → correct model → drill → success metric, with `where` sentences.
2. Rank by `corner_loss_best_vs_ref` *and* consistency (`variance_cliffs`, IQR with `r_with_time`) — the biggest repeatable time.
3. Explain with terrain: `pack.terrain` crests (car light: finish braking before) and dips (car loaded: brake/turn/throttle harder); events carry `terrain[].expected_dg` vs measured `g_vert`.
4. Technique before setup (`diagnosis.order`). Setup levers only for patterns repeating across ≥ 3 clean corners.
5. Speak in landmarks (`coaching.landmarks`): apex-relative metres, car lengths, curated boards — never raw lap metres.
6. Show it: `vre-video-review` (Lap Studio scenes, pins at the exact spot).

## Any track / any car

- Track packs are generated from the game's AI line for every ACC track; curated names/cues/boards live in `vre_rpy/track_pack/notes/<track>.json` and never change the maths.
- Add braking boards when you know them: `"boards_m": {"100": <metres from S/F>}` on the corner's notes (measure by stopping a replay at the board and reading `s_m`).
- Car facts: `vre-car-research`.

**REQUIRED SUB-SKILL:** `vre-teach-answer` for the final answer.
