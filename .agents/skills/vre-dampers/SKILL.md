---
name: vre-dampers
description: Use when the driver asks about dampers (bump, rebound, fast/slow), kerbs or bumps unsettling the car, crests, the car being snappy in transitions or floaty, or wants a final setup dial-in after controls, technique and grip levers are done.
---

# VRE Dampers

**Scope: Physics cross-game; commands and car-file workflow are AC. ACC dampers: `vre-acc-setup`.**

Any car, any track. Dampers do not change how much grip or load transfer the car has in steady state — they change
**how fast** load and ride height move. Tune them for transients (turn-in, brake release, direction changes, crests,
kerbs), and judge them on lap time like any other lever (`vre-setup-and-controls`).

## What each setting does (one wheel)

- **Bump (compression):** how easily the wheel rises into the arch. Soft = absorbs bumps/kerbs, body stays calm.
  Stiff = wheel resists rising, so a bump lifts the whole car and the tyre skips.
- **Rebound (extension):** how fast the wheel drops back to the road. Soft = follows dips and crests, keeps contact.
  Stiff = wheel hangs in the arch over crests/dips (load drops toward zero) and can pack down over repeated bumps.
- **Slow vs fast:** below the knee velocity (AC: `DAMP_FAST_*THRESHOLD`) the slow setting acts — body roll/pitch/heave,
  driver inputs. Above it the fast setting acts — kerbs, bumps, wheel hop. Many AC cars only expose slow dampers.
- **Bump follows the spring:** a stiffer spring needs more bump (and rebound) to stay controlled; compare via damping
  ratio, not clicks.

## Transient balance (the part that changes lap time)

During roll (turn-in, direction changes) the outer damper is in bump and the inner in rebound. The axle with more roll
damping **takes more of the transient load transfer**, so it loses grip first while the car is rolling:
- More rear damping (rear rebound/bump ↑, or front ↓) → turn-in rotation / rear steps out in transitions.
- More front damping → lazy turn-in, transient push, calmer rear.
Steady-state mid-corner balance is set by springs, bars, geometry and diff — not dampers.

**Pace first.** Treat dampers as a **grip lever**: the aim is the least tyre-load variation (wheels following crests,
dips and kerbs) at the end of the car that limits lap time, so the driver can brake later and commit earlier. Calming
the car is never the goal. Any move that removes transient rotation is a trade: keep it only if `compare` shows a faster
median lap; "calmer but slower" ⇒ reject. For a rotation-first driver prefer moves that add compliance/grip at the
limiting end over moves that add front damping (transient push).

**Damper histogram reading (Popometer method):** a good histogram has a tall, narrow centre (~12 % of samples
near 0 mm/s) falling off symmetrically, with almost no high-speed tail. Flat/wide centre → too soft (stiffen springs
first, then dampers). Peak shifted to the rebound side → add rebound damping; to the bump side → add bump.
Widen bins/range before judging (narrow bins look flat). Also check rake: negative rake on turn-in →
sudden aero understeer; lower front bump-stop range limits pitch and stabilises the aero platform. Confirm every
change on track — the histogram is a guide, the lap time decides.

**ACC MoTeC:** use `SUS_TRAVEL_*` @ 200 Hz and `VRE_DV_*` / `VRE_RAKE` from `motec_analysis_ld` (histogram in Motec
worksheets). Do not invent damper velocity from unlocked `.rpy` pose.

Under braking the front goes into bump and the rear into rebound; on throttle the reverse. In **aero cars** this pitch
speed moves the aero platform (stiffer rear rebound keeps rake/diffuser seal longer under braking; stiffer front rebound
keeps the nose down on throttle). In **mechanical-grip cars** (no wings/floor) ignore the aero argument; pitch speed only
matters through geometry (camber) and wheel contact over crests.

## Method

1. Physics first (no laps needed):
   ```bash
   python external/query_tools/driver_lab.py dampers --car <car> [--setup <file.ini>]
   python external/query_tools/driver_lab.py dampers -s <session> [-s ...] --max-lap <cut>
   ```
   It reads the car's wheel rates, ARBs, tyre rates, masses and fuel, then prints ride/roll/hop frequencies, damping
   ratios (zeta) for the driven setup (`setups/<car>/generic/last.ini` by default), fast-damper knees, **roll stiffness %
   front vs roll damping % front**, flags, and every single-click what-if.
2. Rule-of-thumb windows (slow speed): mechanical cars bump 0.3–0.7, rebound 0.5–0.9; aero cars 0.5–0.9 / 0.7–1.3;
   rebound ≈ 1.3–2× bump. These are **starting points to test**, not targets.
3. Telemetry: laps recorded by the current app carry `dampers` (per-frame velocity histograms per wheel and phase, and
   wheel-unload seconds per corner). Read:
   - **sd / spread:** how hard that corner of the car works. Much wider at one end = that end is soft for this track.
   - **Tall narrow peak (high ±10%, high kurtosis)** = stiff for this surface; flat and wide = soft.
   - **Rebound share ≪ bump share** on an axle, with **unload time** at crests = rebound holding the wheel up.
   - **Unload vs section time** per corner: only act where more unload goes with slower passes (|r| ≥ 0.4).
   Older laps have no histograms; the command falls back to 12 Hz inner-wheel unload, which shows lift but not damper speed.
4. Pick **one** move that addresses the flag and fits the driver profile; prefer moves that clear a flag without
   creating one. Make the step big enough to feel (2 clicks or ~0.2 zeta) — one click is usually below lap-time noise.
5. A-B-A with ≥ 5 clean laps each, `compare` verdict. Then bracket (half step back) if it helped.

## Track surface

- Smooth track, few kerbs used: stiffer is usually faster (better platform, sharper response) until the car skips.
- Bumpy / big kerbs / crests: softer, especially rebound relative to bump, so wheels stay on the road.
- Long bumpy corner with oversteer: stiffen the **front** a little (moves transient load transfer forward) rather than
  softening the rear spring/bar.

## Worked example (312/67, Sonoma Long — re-measure on every car)

Stock dampers (never changed by the driver): front zeta 0.49 bump / 0.73 rebound, rear 0.52 / **1.15 rebound**.
Roll stiffness 52% front but roll damping only **31% front** → turn-in and direction changes load the rear first.
Matches the driver's top coast cause "rear stepping out, catch it", entry slides that don't help pace, and the Carousel
braking-on-a-crest problem (an over-damped rear rebound leaves the rear light over a crest).
Test: rear rebound 3 → 1 click (zeta 1.15 → 0.75, roll damping 31% → 37% front), file `..._RR1.ini`, A-B-A vs `..._B57`.
The case is rear **grip** (wheels follow the Carousel crest, steadier rear load so throttle can come earlier), not calm;
it may cost some turn-in rotation. Unproven until `compare` says so — slower ⇒ revert, however calm it felt. The fast dampers are fixed (wheel-hop zeta ≈ 0.12–0.15), so kerbs stay harsh
whatever the slow settings.

**REQUIRED SUB-SKILL:** `vre-setup-and-controls` (order of work, A/B protocol, pace-first verdict) and `vre-teach-answer`.
