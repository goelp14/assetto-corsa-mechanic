---
name: vre-root-cause
description: Use when the driver loses time at a corner, hesitates on throttle, coasts, runs wide, or says a fix in one corner breaks the next — find the upstream cause, not the symptom.
---

# VRE Root Cause

Late throttle, coasting and running wide are almost always **outputs**. The driver lifts or waits because the car is not
pointed, is on the wrong part of the road, or is about to step out. Find which, and what upstream input caused it.

## Method

1. **Rule out controls.** `python external/query_tools/driver_lab.py controls` — brake GAMMA > 1.2 hides light trail braking.
2. **Classify the coasting** (why the driver is off both pedals):

   ```bash
   python external/query_tools/driver_lab.py coast -s <session> [-s ...] --min-lap <a> --max-lap <b>
   ```

   | Cause | Meaning | Fix direction |
   |-------|---------|---------------|
   | A rear stepping out | genuine stability save | entry rotation too violent: smoother release, less engine braking (gear/diff coast) |
   | B front not turning | car stopped rotating, driver waits | keep load on the front: trail brake deeper/lighter |
   | C brake released, gap | pedal swap gap | overlap brake release with throttle pickup |
   | D lift | commitment / fear in fast corners | reference points + progressive commitment |

   On the Sonoma 312/67 data, A was the *smallest* bucket (1.1 s/lap). B+C dominated. Don't assume "saving the car".
3. **Run the corner chain** on fast vs slow passes:

   ```bash
   python external/query_tools/driver_lab.py corner -s <session> --corner "<display name>" --min-lap <a> --max-lap <b>
   ```

   Read the table top-down as a chain: brake on → turn-in speed/brake → **last brake point and coast gap** →
   rear slide after release → understeer entry → min speed → lock → **re-steer after apex** → commit → exit speed.
   Flagged rows (`<==`, |r| ≥ 0.4) are candidates; then check what *they* correlate with upstream.
4. **Read the station profile** (fast block vs slow block every 20 m): where do brake/throttle go to zero together, where
   does the car drift outward (metres right of AI line changes while steer holds), where does understeer rise.
5. **Check elevation** (`driver_lab.py sim` prints crest/compression zones). Braking or releasing over a crest
   (load −40…−80%) causes brake-coast-brake patterns; compressions on exit are where to commit.
6. **Check the next corner** before accepting a gain: correlate this corner's time with the next one's.

Thresholds in `driver_lab` (3° steer, 5% pedal, 0.25 s coast, |r| ≥ 0.4) are car-agnostic defaults. The chains below
are worked examples from one car/track — reuse the method, re-measure the numbers.

## Worked example chains (312/67, Sonoma Long, gamma 1.0 laps)

- **Hairpin (Turn 7):** longer brake-off→throttle gap ⇒ more lock at apex (r +0.61) and less rear rotation (r −0.48) ⇒
  post-apex re-steer (r +0.67 with time, −0.54 with exit speed). Rear rotation reduced lock (r −0.64); the fastest pass had
  ~15° slide. Over-slowing went *with* more re-steer (r −0.40). Fix: no pedal gap; release brake as steering goes in.
- **Long corner (Carousel):** brake released at turn-in, 1.3–1.6 s coast ⇒ nose unloaded, ~3° understeer ⇒ drifts to outside
  edge by the min-speed point with ~135° still to turn ⇒ part throttle and lifts (lifts r +0.55). Later brake release
  (~40 m) = less lock, less coast, faster. Brake zone sits on a crest: brake hard before it, light over it, trail after landing.
- **Exit throttle:** best exits reached full throttle in ~0.6 s once pointed; slow exits fed it in over ~3 s with more lock.
  Wheelspin was not the limiter in 2nd at ~4,900 rpm. "Hesitation" was a pointing problem.

## Pitfalls

- `phase` channel may be unpopulated ("straight"); derive phases from inputs.
- `acc_g_lat` is inflated by kerbs/compressions (2+ g on a no-aero car). For grip use v²·κ from the driven path.
- Samples are ~9 Hz: use ≥ 15–20 m stations and medians, not single samples.
- Lap JSON being written live fails to parse — skip it.
- n ≈ 20 passes: |r| < 0.35 is noise; require consistent multi-station effects.
- Track-config `direction` can be wrong (Sonoma T3 is a left-hander); `driver_lab` uses steering sign instead.

**REQUIRED SUB-SKILL:** `vre-teach-answer`. Say which link in the chain the driver should change, and give a cue.
