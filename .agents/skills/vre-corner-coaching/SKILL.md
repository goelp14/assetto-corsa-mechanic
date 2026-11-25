---
name: vre-corner-coaching
description: Use when the user asks about time loss, corner technique, braking points, visual cues, drills, or what to do at a specific corner.
---

# VRE Corner Coaching

**Scope: Cross-game.**

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

## Driver language (mandatory)

Never give raw lap metres. Translate each point (brake, full pressure, release, turn-in, slowest point, full throttle):

- **Boards** where they exist (ACC: most braking zones have 50/100/150/200 m boards). Only name a board from a curated
  position (`boards_m` in the track notes); geometry-estimated boards were tested and land in the wrong place.
- **Apex-relative:** "117 m before the La Source apex", "13 m after the apex" (track-fixed, exact).
- **Car lengths for differences:** "half a car length later", "7 car lengths earlier (32 m)" — car length ≈ 1.72 × wheelbase.
- ACC replays: `coaching.landmarks.<corner>` and each fix's `where` already say this; reuse those sentences.

Then add a visual cue:

- Scan track objects near the metre value (`kn5` object dump → `objs_on_track.json`: track metre, name, lateral offset)
  and AI/pit-lane geometry (pit-lane split, cones, walls, tyre stacks, kerb starts, crests).
- Express timing relative to the car ("intersection just ahead of the nose", "as the pit lane peels away").
- Mark unverified cues as such ("I haven't seen it from the cockpit").

## Rotation model (read [rotation-and-corner-structure.md](../../docs/coach/rotation-and-corner-structure.md))

Every corner: **braking → closing spiral → MRP (peak yaw rate) → opening spiral**. Rotation should rise as speed
falls; throttle after the MRP. Bundles built since 2026-11 carry per-lap `mrp_m`, `mrp_kmh`, `rotation_jerk_dps2`,
`kmh_lost_turn_in_to_mrp`, `grip_gap_frac`, `last_downshift_vs_apex_m` (`coach/rotation.py`; older bundles:
`python -m external.query_tools.coach.rotation exports/<bundle>`). Use them to say *how* the car is rotated:

- **Snapped vs built** (`rotation_snap`): "1 → 3" jump after turn-in → slide → correction → understeer. Cue: small
  first input, add lock only as the brake bleeds off.
- **Brake straight, then turn** (`brakes_then_turns`): no speed shed while rotating. Cue: carry some brake past
  turn-in and let it go *with* the steering.
- **Grip gap** (`grip_gap_braking_to_turning`): release with no steering waiting. Cue: turn a fraction before each
  step of release; release as long as the steering build. In-car tell: the tyres go quiet.
- **Downshift spread** (`inconsistent_downshifts`): engine braking changes rear bias; same downshift point every lap.
- **Turned in too early** (no metric yet — look for a "waiting" stretch under the limit and a second steering build):
  ask "could the car have taken more steering or trail at turn-in?"
- Steering reductions before the MRP: classify as too slow / no room (losing) vs oversteer (may be fine).
- Never compare raw steering angles between two drivers (wheel lock/ratio settings differ); compare yaw, speed,
  position, and each driver's own balance trend.

- MRP placement guide (share of corner): fast ≈ 49 % MRP / 51 % apex, medium 47/53, slow 45/55; at least half the
  rotation on the brakes before throttle (`rotation_before_throttle_frac`); MRP should coincide with the slowest
  point (`mrp_vs_vmin_m`); a long hold near peak rotation before throttle (`rotation_plateau_s`) is the "maximum
  rotation line" — waiting at half throttle.
- Track-specific knowledge: `docs/coach/tracks/<track>.md` (e.g. Spa) before giving cues.
- Theory and the problem → cause → try table: [car-handling-theory.md](../../docs/coach/car-handling-theory.md).

Give at most **2–3 driving targets per corner** (apex, slowest point, apex 2) — not a list of input changes.

## Lessons from Sonoma 312/67

- "Brake 5 m later" pushed the driver into heavy trail at turn-in → inside-front lock and over-slowing. Brake *where* the
  fast quarter brakes; make it **lighter by turn-in** (≤ 1/3 pedal) instead of later.
- Hairpins: V-line — brake straight, rotate at the slowest point, late apex, full throttle within ~0.6 s once unwinding.
- Long corners: patient entry, light trail to rotation, single progressive throttle squeeze, never lift; let it run
  wide rather than lifting.
- Fatigue shows as over-slowing in a solved corner; recommend a break.

**REQUIRED SUB-SKILL:** `vre-teach-answer`. Read [pedagogy.md](../../docs/coach/pedagogy.md) — max 1–2 fixes.
