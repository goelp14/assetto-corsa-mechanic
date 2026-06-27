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

## F1 / sim racing reading order

1. Where was time lost? → `time_loss.json`
2. Which phase? → speed + inputs for that spline range
3. Who got to power first? → throttle trace vs reference
4. One fix → drill from `session_plan.json`
