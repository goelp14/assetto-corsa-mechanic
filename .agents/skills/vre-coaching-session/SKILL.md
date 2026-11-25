---
name: vre-coaching-session
description: Use when the driver wants a coaching session or debrief ("coach me", "what should I work on", "why am I stuck", plateau, "I'm X seconds off"), wants homework between sessions, or reports back after practising a drill.
---

# VRE Coaching Session

**Scope: Cross-game (AC + ACC).** How to run a session like a good human coach, on top of the analysis skills.
Method from Suellio Almeida's and Nils Naujoks' recorded coaching sessions — see
[pedagogy.md](../../docs/coach/pedagogy.md) ("Coaching, not instructing") and
[rotation-and-corner-structure.md](../../docs/coach/rotation-and-corner-structure.md).

**Read first:** [coaching-craft.md](../../docs/coach/coaching-craft.md) (scenario playbook: beginner, plateau,
hesitant, over-driver, new car, limited time, long track, report-back) and
[car-handling-theory.md](../../docs/coach/car-handling-theory.md) (technique theory with a problem → cause → try
table). Pick the scenario before picking the fix.

## 1. Watch before you talk

- Read the driver's own words first: goal, deadline, what they think is wrong, what they've tried. Keep their
  hypothesis on the table; confirm or refute it with data, never ignore it.
- Look at several laps, not one: habits (`coaching.habits`, `driver_lab.py style`) tell the *pattern*; single
  laps tell incidents. Note which corner *types* share the pattern (heavy-braking hairpins vs fast sweepers).
- Check controls and equipment before technique (`vre-setup-and-controls` / pedal curves). One wrong setting
  can hold a driver back for months.

## 2. Show the reference doing the same thing

- Compare against a lap that shows the idea (`vre-acc-replay-analysis`, Lap Studio video A|B, `vre-video-review`).
  The point is the *mechanism*, not copying their trace — entry conditions never match ("situational driving").
- Rotation questions: read MRP, rotation build, speed shed while rotating, grip gap (`vre-corner-coaching`
  rotation section). Spins: `vre-incident-analysis` slip-angle math.

## 3. Pick the low-hanging fruit — one or two mechanisms

- The biggest *repeatable* inefficiency that explains several corners (style level). Example: "brake straight,
  then turn" shows at Bruxelles, No Name, Pouhon, Stavelot → one fix.
- Explain WHAT (numbers, cited) → WHY (physics, in plain words) → HOW (one drill + 2–3 targets per corner + an
  in-car cue the driver can feel or hear). Tell them what they'll feel when it works.
- Give them a diagnostic question to ask themselves in the car ("could the car have taken more steering at
  turn-in?").

## 4. Drill, then homework

- Short drill block with a success metric (`coaching.fixes[].success_metric`), then homework: ~50–100 laps on
  that one thing, then a fresh replay/lap for the retest.
- Warn that it gets worse before it gets better; spinning while learning the limit is part of it. Judge balance
  control first, lap time after adaptation.

## 5. Retest and close the loop

- On the next replay/session: same metric, same corner(s); say plainly whether it moved and by how much
  (`driver_lab.py compare` / new bundle vs old).
- If it moved and time didn't, look downstream (the next corner, the straight); if it didn't move, the cue didn't
  land — change the cue, not the goal.
- Record what worked in the driver profile (`vre-driver-profile`) and notes (`vre-annotate-replay`).

## Never

- Instruct without the why ("brake here, turn there") — the driver must be able to repeat it on a new track.
- Hand over a corner-by-corner list of 5+ changes.
- Tell them to copy a reference trace.
- Recommend a calmer setup to cover a technique gap (pace first).

**REQUIRED SUB-SKILL:** `vre-teach-answer` for the final response.
