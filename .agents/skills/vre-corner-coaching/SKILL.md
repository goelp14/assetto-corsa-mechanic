---
name: vre-corner-coaching
description: Use when the user asks about time loss, corner technique, braking points, visual cues, drills, or what to do at a specific corner.
---

# VRE Corner Coaching

Corner-scoped technique and pace coaching. The answer is one drill plus a visual cue the driver can actually see.

## Evidence priority

1. Driver's own fast-vs-slow passes: `driver_lab.py corner -s <session> --corner "<name>"` (live/archived sessions)
2. Bundle: `session_plan.items`, `time_loss_corners`, `corner_reports`, `pace_opportunities`
3. Typical-vs-best gap per corner (where consistency, not peak, is the loss)

## Analysis pass

1. **Where lost?** Rank by fast-vs-slow section gap *and* typical-vs-best gap.
2. **Measure on a fixed section that includes the exit straight.** Exit speed dominates slow corners (Turn 11: exit speed,
   not apex speed, decided time).
3. **Which link?** Run `vre-root-cause` when the loss is exit/hesitation/coasting — don't stop at "throttle earlier".
4. **Choose what's repeatable, not the single best pass.** Pick the braking point/turn-in that the *fast quarter* shares
   and that has low spread; avoid cues taken from one outlier lap.
5. **Coupled corners:** check the next corner's time before recommending more speed (complexes = one corner).

## Visual cues (mandatory)

Drivers have no distance boards. For each point (brake, turn-in, release, rotation point, apex, commit):

- Scan track objects near the metre value (`kn5` object dump → `objs_on_track.json`: track metre, name, lateral offset)
  and AI/pit-lane geometry (pit-lane split, cones, walls, tyre stacks, kerb starts, crests).
- Express timing relative to the car ("intersection just ahead of the nose", "as the pit lane peels away").
- Mark unverified cues as such ("I haven't seen it from the cockpit").

## Lessons from Sonoma 312/67

- "Brake 5 m later" pushed the driver into heavy trail at turn-in → inside-front lock and over-slowing. Brake *where* the
  fast quarter brakes; make it **lighter by turn-in** (≤ 1/3 pedal) instead of later.
- Hairpins: V-line — brake straight, rotate at the slowest point, late apex, full throttle within ~0.6 s once unwinding.
- Long corners: patient entry, light trail to rotation, single progressive throttle squeeze, never lift; let it run
  wide rather than lifting.
- Fatigue shows as over-slowing in a solved corner; recommend a break.

**REQUIRED SUB-SKILL:** `vre-teach-answer`. Read [pedagogy.md](../../docs/coach/pedagogy.md) — max 1–2 fixes.
