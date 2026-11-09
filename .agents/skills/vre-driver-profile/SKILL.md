---
name: vre-driver-profile
description: Use at the end of every session, before any setup recommendation, and when the driver asks about their driving style, how it is trending, or what kind of driver they are.
---

# VRE Driver Profile

A persistent, car-agnostic record of how this driver drives, built from data every session and used to tailor coaching
and setup. Stored at `ac_app/data/driver_profile.json` (gitignored; override with `VRE_DRIVER_PROFILE`).

## Update it

```bash
python external/query_tools/driver_lab.py style -s <session> [-s ...] --min-lap <a> --max-lap <b>
# record what the driver tells you they want (persists across cars):
python external/query_tools/driver_lab.py style -s <session> --prefer "wants a car that rotates; never trade pace for stability"
```

Run it on clean laps of one setup/controls group. Use `--no-save` for exploratory runs.

## Metrics (all relative, comparable across cars)

| Metric | Meaning |
|--------|---------|
| `entry_slide_deg`, `slide_helps_r` | rear slide after brake release on the fastest passes; r < 0 ⇒ sliding goes with faster passes |
| `brake_at_turn_in`, `trail_m` | trail-braking depth and length |
| `pedal_gap_s` | brake-off → throttle-on coast per corner |
| `v_ratio`, `throttle_ramp_s` | min speed ÷ turn-in speed, and 20→95% throttle time on best exits (V vs U) |
| `re_steer_deg` | steering added after the apex (car not pointed) |
| `fast_corner_gap_pct` vs `slow_corner_gap_pct` | typical-vs-best min speed gap by corner speed (commitment) |
| `coast_*_s` | coasting per lap by cause (rotation wait, pedal swap, lift, save) |
| `consistency_pct` | (median − best) / best |

The command prints labels (rotation-first / stable-rear, V / U / mixed, trail-braker type, commitment bias, pedal gaps),
a **setup fit** line, trend vs the previous entry for the same car+track, and traits that stay constant across all
cars and tracks.

## Use it

- **Setup:** pass `setup fit` and preferences into `vre-setup-and-controls`. A rotation-first driver gets pace/rotation
  levers, never stability levers that cost time.
- **Coaching:** pick drills that extend the natural style (a V-driver learns pedal overlap and late apex, plus a patient
  U in long corners) rather than converting them to another style.
- **Trend:** report what improved (e.g. pedal_gap_s falling) and what is constant across cars — constant weaknesses are
  the real habits.
- **Comparisons to famous drivers:** map labels to reputations (see `vre-pace-potential`), and say they are reputations.

## Honesty rules

- Labels come from thresholds; when a metric sits near a threshold, say "mixed" instead of forcing a category.
- Stated preference ≠ measured style. Record both; if they disagree (e.g. driver wants rotation, data shows stable-rear
  entries), that gap is a coaching opportunity, not an error.
- One session is one sample. Talk about traits only once they repeat across sessions.

**REQUIRED SUB-SKILL:** `vre-teach-answer`
