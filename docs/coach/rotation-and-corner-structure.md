# Rotation and corner structure (closing spiral → MRP → opening spiral)

The rotation model behind `coach/rotation.py`, the `build_rotation` / `rotate_then_throttle` /
`commit_or_rotate` fixes and the "Rotation" habits. Synthesised (own words) from Suellio Almeida's coaching
videos and Nils Naujoks' (Popometer) ACC coaching and telemetry videos, 2026-11. Car- and track-agnostic.

## 1. The corner is four phases, every time

**Braking zone → closing spiral → Maximum Rotation Point (MRP) → opening spiral.**

- Speed sets the radius the car can hold: slower = tighter. While the car decelerates it can rotate more and
  more, so the line *closes* (spiral, not a circle). Once accelerating it can rotate less and less, so the line
  *opens*. The line is an ellipse-like shape, not a constant-radius arc.
- **Rotation must be inversely linked to speed.** As speed falls, rotation rises roughly linearly:
  "1-2-3-4-5 → power → 4-3-2-1". The common fault is "1 → 3": a big early jump of rotation the speed can't
  support yet → the rear slides → correction → then understeer ("understeer–snap–oversteer" cycle).
- **MRP = peak yaw rate**, not the apex. Usually a little before the apex. Throttle
  belongs after it; the throttle's job is to open the spiral.
- **Turn once.** Never stop *increasing* the steering until the MRP. Building a bit of lock, holding, building
  again ("several small lines") means each pause is spent under the limit.

## 2. Where rotation comes from

- **Brake release unlocks rotation.** In ABS/at the front limit, more steering adds nothing; releasing a
  little brake lets the fronts "breathe" and the car turns with the same lock. Technique: a small steering
  block, a moment of brake, release → the car rotates; add the next block; release; repeat at high frequency.
  Looks like steering and brake moving together ("string theory": brake release tied to steering angle).
- **Every rotation is paid for with speed.** Trail braking trades speed for rotation — pay as little as
  possible ("be cheap"): the least brake and the least steering that give the rotation.
- **Anything wrong gives understeer**: too much brake (ABS/front overload), too little (no front load), early
  part throttle (10–20 % mid-corner kills rotation), too slow (no load to turn with). To point the car mid
  corner: off throttle, touch the brake (1 %), it points, back on.
- **Turning in too early** creates a "waiting" phase: not braking hard (no room), not turning (would cut
  inside) → under the limit, indecisive inputs, ABS, over-slowing, inconsistency. Turn in later, give yourself
  the room, then build the spiral decisively. Diagnostic question: *at turn-in, could the car have accepted
  more steering or more trail?* If yes → turned in too early or too slow.

### Three rotation tools: steering, brake, engine

- **Engine braking acts on the rear axle only**, so downshift timing changes the effective brake bias
  ("dynamic brake bias"). Brake 3–5 % softer and downshift earlier/harder → more rotation at turn-in; downshift
  later → calmer car. Decide it per corner (understeery corner: earlier downshift; sketchy corner: later) and
  repeat it. Downshifts landing in different places each lap = a different balance each lap = inconsistency.
- **Three ways to combine brake release and steering:** (1) release, then turn → a gap with no grip used →
  understeer (and "too safe", stuck at a plateau); (2) start turning as you start releasing; (3) a little
  steering *before* each step of release (0.1–0.2 s) — with ABS, getting off the ABS with lock already on turns
  the car a lot. (2) and (3) are where the time is; which works depends on car/setup — try both.
- **Release length ≈ steering-build length.** A quick brake drop leaves the car under the limit for a moment
  and over it the next, wherever you place it. Low-downforce: long, gradual release; high-downforce: quicker
  initial drop but not to zero.
- **"Make it turn" vs "let it turn".** Same pedal trace, different trigger: release the brake *because you want
  more rotation now* (let the fronts breathe), not hold it because you'll want rotation later.
- **If the car doesn't turn with more steering, stop adding it.** Go back to ~1 % brake and wait; more lock only
  heats the fronts. Coast only when the rotation is already enough — coasting gives up the brake as a tool.
- **Grip-usage gap** (heard as the tyres going quiet between braking and turning): the tell that brake and
  steering aren't synchronised, or that you braked too early (released with nowhere to turn yet).

### Read the driver at style level, not corner by corner

A driver's habits repeat in every corner of the same type (heavy-braking hairpins, fast sweepers…), and can be
opposite between types. On a long track coach the *technique pattern* that applies to all corners of a type;
then sync the styles across types. Our habit detector works exactly this way (≥ 3 corners or ≥ half the laps).

## 3. Steering corrections — classify them

A steering reduction before the MRP happens for one of three reasons:

| Reason | Meaning | Lap time |
|---|---|---|
| Too slow | over-slowed, car would cut inside | losing |
| No room | turned in too early | losing |
| Oversteer | car rotated more than asked | may still be a fast lap |

Only "oversteer" corrections are compatible with being on the limit.

## 4. Oversteer, understeer and slip angle (why the fast setup is the loose one)

- Understeer = fronts past their optimal slip angle (more steering → *less* lateral force, tyres scrub/heat).
  An understeering car can't be brought to neutral without over-slowing it.
- A loose car can be held at **neutral steer / micro-oversteer** with weight transfer and inputs → more
  speed. Fast drivers aren't reacting faster; they *predict* where oversteer is likely and prepare.
- Snap oversteer happens most at **early entry** (heavy front load from trail + tense hands → too much
  rotation) and **late exit** (gaining speed while asking for constant rotation — circle thinking).
  Fixes: light hands on turn-in; take the rotation at low speed (early exit) so you don't have to force it
  at higher speed later; fear of the exit spin causes hesitation that causes the exit spin.
- Front slip ≈ body slip + steering angle (same sign). While sliding, extra lock in the slide's direction
  overloads the fronts and *kills* rotation; counter-steer too small/too slow still leaves the fronts
  generating inward force → spin. Corrections must be quick enough to catch the slide angle.

## 5. Two or three targets per corner (Popometer "track marks")

Too much information can't be used in the car. Give the driver per corner only:

1. **Apex 1** — closest point to the inside edge,
2. **Slowest point** — where deceleration stops (needs *enough* throttle to actually accelerate: 40–50 %
   in ACC may only cancel engine braking),
3. **Apex 2** (long / double-apex corners).

Typical faults: apex 1 missed; slowest point too early, leaving 2/3 of the corner to "accelerate through"
(car can't, so it reaches apex 2 early and runs out of road); slowest point after the apex (should be
slightly before it — accelerate through the apex).

## 6. Braking patterns that cascade (Popometer)

- Braking later carries extra speed → turn in early to "extend" the braking zone (diagonal line) → car hasn't
  rotated by the apex → late throttle → loss on the straight. Fix the braking point, then straight-line
  brake parallel to the outside kerb.
- Slamming the brake while already turning overdrives the front → understeer → release → front bites → rear
  steps out → driver adds lock. Respect the friction circle: with 40 % of grip used turning, ~60 % braking.
- In long corners: a gentle 5–20 % brake input carried through the corner pitches the car and keeps the
  line tight; one harsh input forces an early straight-line brake and a lower speed never recovered.
- A second short brake input mid-complex can tighten the line to open the more important next corner.
- One error upstream (variable exit speed) moves every later braking point: fix the corner before.
- Sequence for lift-only corners: **start turning before lifting**, and don't lift fully — load the
  outside rear first; lifting and turning together hits the car when it's most vulnerable.

## 7. How the metrics map (coach/rotation.py)

| Lesson | Metric | Habit |
|---|---|---|
| MRP location / speed | `mrp_m`, `mrp_vs_apex_m`, `mrp_kmh`, `mrp_yaw_dps` | `rotates_at_lower_speed` |
| "1 → 3" snap vs built rotation | `rotation_jerk_dps2` (peak yaw acceleration turn-in → MRP) | `rotation_snap` |
| Brake straight, then turn | `kmh_lost_turn_in_to_mrp`, `heading_to_mrp_deg` | `brakes_then_turns` |
| Throttle after rotation | `throttle_on_vs_mrp_m` | `throttle_before_rotation` |
| Throttle proportional to unwind | `steer_unwind_at_full_throttle` | (descriptive) |
| Part throttle that doesn't accelerate | `maintenance_throttle_s` | `maintenance_throttle` |
| Slide on entry | `entry_slip_peak_deg` | evidence on `rotation_snap` |
| Slowest point vs apex | `vmin_vs_apex_m` (vre-rpy) | `over_slowing` |
| Grip-usage gap braking → turning | `grip_gap_frac` (dip in combined g before the MRP) | `grip_gap_braking_to_turning` (needs own-lap r ≥ 0.4) |
| Dynamic brake bias consistency | `last_downshift_vs_apex_m` (IQR) | `inconsistent_downshifts` |
| Release length vs steering build | `brake_release_vs_steer_build` | (descriptive — noisy on Spa) |
| Balance (intent vs response) | `understeer_entry` = 1 − achieved / asked curvature, steering gain fitted per lap | (descriptive — noisy on Spa) |

**Balance trace** (Almeida 3D analyzer idea): steering angle is the *intention*, yaw rate the *response*. We fit
each lap's steering gain in the near-linear range (|g_lat| < 0.5) so different wheel lock/ratio settings
cancel out, then compare asked vs achieved curvature. Steering *force* (driver torque = steering motion
explained by neither FFB nor inertia — shows light hands and passive counter-steer) needs the FFB torque
channel, which ACC replays don't record; possible from live shared memory / MoTeC later.

Rotation-build metrics are only computed in braked corners. Cross-driver *steering angle* comparisons are
not used: wheel lock/ratio settings differ between drivers; yaw, speed and position don't.

Rotation-before-throttle share (`rotation_before_throttle_frac`), the Maximum Rotation Line
(`rotation_plateau_s`: rotation held ≥ 85 % of peak before the throttle) and MRP vs slowest point (`mrp_vs_vmin_m`)
follow the book's rules (≥ 50 % rotation on the brakes; MRP = minimum speed = throttle point). Habit
`accelerates_before_half_rotation` fires only where the reference does rotate ≥ 50 % first.

General theory behind all of this: [car-handling-theory.md](car-handling-theory.md); how to teach it:
[coaching-craft.md](coaching-craft.md); track specifics: [tracks/](tracks/).

## 8. Sources

- Suellio Almeida — *Advanced Coaching – Are you REALLY on the limit?* (youtube.com/watch?v=1JxWNPDITWc)
- Suellio Almeida — *Why OVERSTEER is faster than understeer* (SD8SZ5qNLtY)
- Suellio Almeida — *This racing physics video will break your brain* (GHkP2fGldno)
- Suellio Almeida — *Most drivers underestimate this little technique* (vnwxGdQsMFM): engine braking, release timing
- Suellio Almeida — *Advanced GT3 driving technique – coaching session* (qIqmo-z7GOE): grip gap, three ways, style-level coaching
- Suellio Almeida — *You'll never look at telemetry the same way* (85kAyM4vDgk): 3D analyzer, balance trace, steering force
- Nils Naujoks — *Common driving mistakes – 10 examples from coaching* (M_Q2HvFv2OA)
- Nils Naujoks — *Telemetry is underrated – simplified insights* (WfbXARdpO2o)
- Nils Naujoks — *How to analyze your data – Part 1 Braking* (tVXSGbqXlKw)
- Nils Naujoks — *How to use the damper histogram* (dPZ4YEPYs3M) → see `vre-dampers` / `vre-acc-setup`
- Almeida Racing Academy blog (MRP, light hands, trail braking)
