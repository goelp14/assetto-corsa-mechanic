---
name: vre-setup-and-controls
description: Use when the driver asks for a setup change, says the car or inputs feel wrong, suspects miscalibration, wants more pace from setup, or after spins tempt you to "calm the car down".
---

# VRE Setup and Controls

Any car, any track. The goal of setup is **lap time the driver can repeat**, never "fewer slides".

## The mistake this skill exists to prevent

On the 312/67 at Sonoma every spin was answered by calming the car (softer bars, more diff coast lock, more forward
brake bias). The car got more stable and **slower**; the driver's best laps came on stock + a gearing change.
Causes of the mistake:
1. Treating slides as the problem instead of a symptom (the root cause was a brake gamma of 2.4 + pedal gaps).
2. Only touching stability levers; pace levers (pressures, camber, gearing, ride height, springs, front grip) untried.
3. Judging variants while the driver was also learning, changing wheel settings and technique, with cold-tyre laps mixed in.

## Order of work

1. **Controls:** `python external/query_tools/driver_lab.py controls`. Brake/throttle GAMMA should normally be 1.0
   (AC: output = pedal^gamma; 2.4 turns 20% pedal into 2% brake). After fixing controls, **re-test the base setup** —
   earlier changes may have been compensations.
2. **Technique root cause** (`vre-root-cause`): if slides/coasting come from pedal gaps or entry habits, a setup change
   only masks them and costs pace. Give the driving fix ~10 laps first.
3. **Driver profile** (`vre-driver-profile`): read `setup fit` and stated preferences. A rotation-first driver must not
   be given an understeery, "safe" car.
4. **Only then** pick one setup lever.

## Lever classes

Read real ranges/units from the car first (`tools/extract_car_profile.py`, car `setup.ini`); skip levers the car lacks.

| Class | Examples | Default stance |
|-------|----------|----------------|
| **Pace / grip** | tyre pressures into the window, camber for even temps, gearing per corner/straight, ride height/rake, spring/damper balance for bumps & kerbs, aero balance (aero cars) | **Try these first** — they add grip or drive without removing rotation |
| **Rotation / response** | rearward brake bias, less diff coast/preload, stiffer rear bar, softer front bar, front toe-out | Use when the driver wants more rotation or fights mid-corner push |
| **Stability** | forward brake bias, more diff coast/preload, softer rear bar, stiffer front bar, rear toe-in, more rear wing | **Pace-costly.** Only with evidence the instability costs more time than the lost rotation, and never for a rotation-first driver whose fast passes include rear slide |

## A/B protocol (mandatory before calling a change good or bad)

1. One change per variant, new file `<base>_<change>.ini`, diff it to prove one line changed.
2. ≥ 5 clean laps per variant, tyres in window (skip the first 1–2 laps of a run), same controls and same drill.
3. Prefer **A-B-A** (or B-A-B) so practice doesn't flatter the later variant.
4. Run:

   ```bash
   python external/query_tools/driver_lab.py compare -a <session>:<laps A> -b <session>:<laps B> --max-lap <cut>
   ```

5. **Verdict rule (pace first):** accept B only if median lap is faster beyond noise, or equal pace with clearly better
   style fit/confidence. **"More stable but slower" ⇒ reject**, even if the driver spins less. Fewer slides is a
   constraint to satisfy (the driver must finish laps), not the objective.
6. Read per-corner deltas: a change that gains in slow corners and loses in fast ones (or vice versa) is a trade, say so.
7. Respect the driver's call when pace is equal (e.g. they kept diff coast 40 because it rotated the way they like).

## Examples (312/67, Sonoma Long — re-measure on every car)

- Gamma 2.4 → 1.0: slides 1.5 → 0.5 /lap, turning-coast 12.7 → 8.1 s/lap; median pace unchanged in a 4-lap sample
  (compare said inconclusive — don't over-claim from a best lap).
- Brake bias 59 → 57: no pace difference within noise (0.15 s vs 0.43 s noise); not a proven gain.
- Shorter 4th gear (VRE_Sonoma_Pace): first sub-1:35 and the most consistent block — a pace lever, not a stability one.

**REQUIRED SUB-SKILL:** `vre-teach-answer`. State the single change, its lever class, what to feel for, the lap count,
and the compare verdict when available.
