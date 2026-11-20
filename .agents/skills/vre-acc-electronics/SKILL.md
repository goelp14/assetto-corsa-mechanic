---
name: vre-acc-electronics
description: Use for ACC GT3 TC1/TC2, ABS, ECU maps — especially ferrari_296_gt3 — only after mechanical balance; never calm-only bumps.
---

# VRE ACC Electronics

Electronics **amplify** balance; they do not fix wrong springs, pressures, or diff.

## Sources

- `ac_app/config/acc/gt3_physics_kb.json` — fact `electronics_tc_abs`
- `ac_app/config/acc/cars/ferrari_296_gt3.json` — `electronics_bands`, **`steering_lock_deg`: 400** (1.9.3 fix)
- `ac_app/config/acc/kb_loader.py` — `load_car_profile("ferrari_296_gt3")`

Post-**1.9** / KB **1.10.3**. Reject pre-1.9 dogma via `reject_pre_19_advice` when quoting external setup sheets.

## 296 typical bands (starting hypotheses — verify on telemetry)

| Map | Band | Pace-first note |
|-----|------|-----------------|
| TC1 | 2–5 | Lower = more cut; pick **minimum** intervention that exits at pace |
| TC2 | 4–7 | Slip tolerance; tune with diff exit + rear grip |
| ABS | 3–6 | Trail-brake limit; pair with bias/migration |

## Rules

1. **Settings ≠ state.** TC=7 / ABS=2 are **maps** (`VRE_TC_LEVEL` / `VRE_ABS_LEVEL`). Motec TC/ABS 0–1 and HUD InAction are **active** (`VRE_TC_ACT` / `VRE_ABS_ACT`). Tune maps from intervention that **costs lap time**, not from feeling nervous.
2. **No calm-only TC/ABS increase** unless `tc_cutting` / `abs_locking` telemetry shows **lost lap time** (intervention counts vs throttle, lock spikes). Sonoma lesson: calm-only setup made the car slower — same doctrine here.
3. **`tc_cutting` costing exits:** Small TC2 step or diff exit before stacking TC1 — one change per A/B test. Mechanical first when TC fights the diff.
4. **`abs_locking` under trail:** ABS map or bias/migration — not wing.
5. Steering lock **400°** affects apex references in line coaching; not an ECU lever.
6. Motec path: **Wheelspeed** worksheet + Compare overlays (`acc-motec-pace-setup.md`).

Hints CLI:

```bash
python -m external.query_tools.acc_ingest.setup_hints --symptom tc_cutting --car ferrari_296_gt3
```

## A/B

```bash
python external/query_tools/driver_lab.py compare -a <session>:<laps A> -b <session>:<laps B>
```

Prefer **A-B-A**. Reject "smoother but slower."

**REQUIRED SUB-SKILL:** `vre-acc-setup`, `vre-acc-tyres` (tyres first if out of window); `vre-teach-answer`.