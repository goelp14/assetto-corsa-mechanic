---
name: vre-corner-coaching
description: Use when the user asks about time loss, corner technique, drills, or what to do at a specific corner.
---

# VRE Corner Coaching

Corner-scoped technique and pace coaching.

## Evidence priority

1. `session_plan.items` — ranked drills
2. `time_loss_corners` — loss_s, primary_action
3. `corner_reports` — WHAT/WHY/HOW vs reference
4. `pace_opportunities` — clean but slow (cyan)

## Analysis pass (industry standard)

1. Where lost? → time_loss rank
2. Which phase? → entry / mid / exit from report
3. Throttle vs reference? → sector_bests phases
4. One drill → session_plan or report action

## Compare to reference

```bash
python -m external.query_tools.coach pack --bundle ... --corner t7
```

Check `sector_bests` phase metrics for same corner.

**REQUIRED SUB-SKILL:** Use `vre-teach-answer`

Read [pedagogy.md](../../docs/coach/pedagogy.md) — max 1–2 fixes.
