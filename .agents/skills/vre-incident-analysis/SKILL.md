---
name: vre-incident-analysis
description: Use when the user asks why they spun, crashed, lost control, or had a high-beta incident.
---

# VRE Incident Analysis

Deep-read loss-of-control evidence.

## Steps

1. Load `analysis/incidents.json` from bundle
2. Filter by corner/lap if scoped
3. For top incident, analyze:
   - `peak_beta_deg`, `phase`, `spline`
   - `pre_window[]` — throttle, steer, acc_g_lat, susp_min before spike
   - `hypotheses[]` — ranked causes
   - `vs_reference` — delta vs best lap at same spline

4. Map hypothesis to template: `root_loss_of_control`, throttle-under-lateral, kerb_unload

## Key thresholds

From `ac_app/config/thresholds.json`:

- `BETA_TERMINAL_DEG`: 35° — loss of control
- `BETA_INTENTIONAL_MAX_DEG`: 25° — intentional rotation ceiling

## Mechanism explanations

Read [dynamics-glossary.md](../../docs/coach/dynamics-glossary.md):

- Throttle + lateral G → rear overload
- Kerb → inside tyre unload
- Steer fight → exceeded grip envelope
- **Coast at speed into a corner** → no axle loaded; in low gears engine braking loads only the rear → snap
  (Carousel spin from a 1.3 s coast at 159 km/h)
- **Downshift at high speed** → rear lock/snap; check `gear` change + rear long-slip spike in the pre-window
- **Abrupt brake release at turn-in** (≥ 50% → 0 in one station) → rear steps out in 2nd-gear hairpins
- **Braking over a crest** → load drop → lock or float (check `driver_lab.py sim` crest zones)

## Before blaming the driver

Run `python external/query_tools/driver_lab.py controls`. A non-linear brake curve (GAMMA > 1.2) makes trail braking
impossible to modulate and shows up as repeated coast-then-snap incidents.

## Cluster, don't anecdote

If the same corner shows incidents on several laps, run `driver_lab.py corner` on that corner and compare incident passes
with clean fast passes — the incident is usually the extreme of a habit visible on every lap.

**REQUIRED SUB-SKILL:** Use `vre-teach-answer`
