---
name: vre-line-analysis
description: Use when the driver asks about their racing line, turn-in point, apex, track-out, or whether to be further left/right somewhere.
---

# VRE Line Analysis

Judge lines from the driver's **own** passes, not from the AI line. The AI line is only a fixed ruler for measuring
lateral position.

## Command

```bash
python external/query_tools/driver_lab.py lines -s <session> [-s ...] --min-lap <a> --max-lap <b> [--corner "<name>"]
```

It samples lateral position (+ = driver's right) every 10 m, correlates it with section time, and only reports runs of
≥ 3 consecutive stations with |r| ≥ 0.40, labelled "toward inside/outside" using the corner direction from steering.

## Why this method

- **Edge distances from `fast_lane.ai` are unreliable** for absolute claims: side widths are rough, "left/right" labels
  are flipped relative to the driver on some tracks, and pit-lane splits create fake −10 m "off-track" readings.
  First attempts using edges produced apexes at turn-in and impossible exits. `driver_lab` calibrates the right-hand side
  from steering and avoids edges.
- **Single-sample apex detection fails** at ~9 Hz; fixed stations + medians are stable.
- **Multiple comparisons:** ~40 stations × 20 passes will throw a couple of false |r| ≥ 0.4 hits per corner — hence the
  3-station run rule.

## Interpreting

1. **"No consistent line difference"** ⇒ time is speed/commitment there; send to `vre-root-cause`, don't invent a line fix.
2. **Slow passes both slower AND wider mid-corner** ⇒ early/tight turn-in (strongest evidence of a line error).
3. **Position difference with a big speed difference** may be a consequence of speed (braking zones especially).
4. **Recurring pattern to look for:** tight/early entry → wide middle → part throttle. On Sonoma it appeared at T2, T7,
   Carousel entry and T3a exit. The cure is the same everywhere: later/wider turn-in, rotate first, late apex (V).
5. **Distinguish rotation point from apex.** At Sonoma T11 the fast passes were ~8 m *wider* at the tyre stacks
   (slowest point) and clipped the inside ~50 m later. Calling the stacks "the apex" was wrong; they are the rotation cue.
6. **Range check:** if the driver never tried the alternative line (e.g. all Carousel entries within ±1.8 m), say so and
   propose a 5-lap test with a success criterion (e.g. "stay a car width inside the outside edge mid-corner").
7. **Consistency:** report the per-corner spread; most drivers are within 0.5–1.3 m — the high-spread spots are usually
   where the gain is.

## Output

Per corner with a finding: where (metres → landmark), which way, by how much, what it bought (section time / exit speed),
and confidence. Group "no line issue" corners in one sentence.

**REQUIRED SUB-SKILL:** `vre-teach-answer`
