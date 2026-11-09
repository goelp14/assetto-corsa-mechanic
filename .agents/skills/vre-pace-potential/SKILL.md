---
name: vre-pace-potential
description: Use when the driver asks how fast they could go, how far from alien pace they are, what lap time is achievable, or what their driving style is compared with top drivers.
---

# VRE Pace Potential and Style

## Achievable lap time

```bash
python external/query_tools/driver_lab.py sim -s <session> [-s ...] --min-lap <a> --max-lap <b>
```

The sim runs on the AI line with elevation (grade + crest/compression load), using the driver's **measured** braking,
acceleration and per-corner lateral grip (from v²·κ of their own path — never raw `acc_g_lat`).

1. **Calibrate first:** sim at median-lap grip vs real median lap = transition loss (pedal gaps, coasting). Sim at best-pass
   grip should land near the stitched best sections. If it is off by > 0.5 s, say the estimate is weak.
   Example (312/67 Sonoma): 94.6 s vs 96.15 s real median ⇒ ~1.5 s/lap loss; best-pass sim 93.4–93.6 vs stitched 93.76.
   Aero cars: the sim uses constant μ per corner from measured grip, so it captures aero only through the driver's own
   corner speeds — treat the ceiling as conservative there.
2. **Bands:** add 0.5–0.8 s transition loss even for fast drivers. Report tiers: transitions fixed at current grip;
   plus fast-corner commitment (+3–5% grip there); physics ceiling (sim, zero loss — not repeatable).
3. **Where grip pays:** per-corner "+5% grip value" ranks corners — slow and long corners usually beat quick ones.
4. **Elevation:** list compressions (commit/brake harder) and crests (be light/patient). Tie them to the driver's
   observed behaviour (e.g. brake-coast-brake on the Carousel crest).

## Alien comparison

- Search for a public leaderboard for the exact car+track (Track Titan, AssettoGrid, acleaderboard, VenueLaps). Many pages
  are JS-rendered and won't fetch; say so rather than guessing.
- Without a benchmark, give a clearly labelled estimate (aliens typically 2–4% faster than a solid club driver) and suggest
  a combo with a public board to calibrate.
- Evidence of potential worth citing: progression over sessions, stitched-best gap, accurate self-diagnosis by feel,
  speed of learning a fixed corner.

## Style profile

Run `driver_lab.py style` (see `vre-driver-profile`) for measured traits and the cross-session trend, then map to
commonly described driver archetypes (label them as reputations, not measurements):

| Trait | Evidence |
|-------|----------|
| Rotation-first entry, tolerates rear slide | fastest passes with 10–15° rear slide; prefers rearward bias / low diff coast |
| V vs U | hairpins improve with late apex + early straight-line throttle |
| Throttle decisiveness | time 20%→95% throttle on best exits |
| Fast-corner commitment | lift-coast seconds in fast corners; min-speed spread there |
| Slow vs fast corner strength | per-corner grip use and fast-vs-slow gaps |

Archetypes: **rotation/V** — Verstappen (pointy front, loose rear), Leclerc, Hamilton (late braking, rotation on brakes),
Schumacher. **Flow/U or front-led** — Alonso (loads the front, drives through understeer), Button/Prost (smooth,
stable rear), Räikkönen (needs a strong front end), Vettel 2010–13 (planted rear).

Always state the gap to the archetype in concrete terms: V-drivers who are fast never leave the car without a pedal
loading an axle, and are committed in fast corners; they switch to a patient U in long corners.

**REQUIRED SUB-SKILL:** `vre-teach-answer`
