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

**REQUIRED SUB-SKILL:** Use `vre-teach-answer`
