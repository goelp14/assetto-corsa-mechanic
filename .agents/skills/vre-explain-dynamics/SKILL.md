---
name: vre-explain-dynamics
description: Use when the user asks why something happened mechanically — understeer, oversteer, grip, tyres, load transfer.
---

# VRE Explain Dynamics

Ground mechanism explanations in evidence + glossary.

## Rules

1. Start from a metric in the evidence pack — never parametric-only physics
2. Link metric → mechanism → driver action
3. Read [dynamics-glossary.md](../../docs/coach/dynamics-glossary.md) for vocabulary

## Common chains

| Observation | Mechanism | Fix |
|-------------|-----------|-----|
| High throttle + high acc_g_lat | Rear overloaded while turning | Wait for G to fall |
| High beta at exit | Power before unwind | Straighten wheel first |
| susp_min in kerb band | Tyre unloaded | Avoid kerb or pause inputs |
| delta_us positive | Understeer | Trail brake longer or reduce entry speed |
| delta_us negative | Oversteer | Smooth throttle, reduce steer rate |

## Evidence fields

`beta_deg`, `acc_g_lat`, `delta_us_deg`, `throttle`, `susp_ratio`, `peak_ay_g`

**REQUIRED SUB-SKILL:** Use `vre-teach-answer`
