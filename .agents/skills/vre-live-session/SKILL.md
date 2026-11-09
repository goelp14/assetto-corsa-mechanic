---
name: vre-live-session
description: Use when the driver is on track and laps are arriving (monitor notifications, "next lap", lap-by-lap coaching).
---

# VRE Live Session

## Setup

- Run a background monitor over the live session dir that prints one block per lap
  (`LAP n time`, vs session best/PB, grip used, coast split, per-corner loss vs fast-quartile median with vmin, coast,
  exit grip, time to full throttle). Notify on `^(LAP|Traceback|SESSION)`.
- Read its output from the terminal file; if the shell has flipped to PowerShell, read via `\\wsl.localhost\...` paths and
  re-check with `echo $SHELL` before running Python.
- Keep the PB constant in the monitor in sync with the real (valid) PB; AC's stored PB can differ from an invalid on-screen PB.

## Per-lap reply (keep it short)

1. Lap time and delta in one line; say if invalid/off and where.
2. **At most one** focus for the next lap, tied to the current drill. Don't change the drill every lap.
3. Repeat the visual cue, not metres.
4. Mention setup only between runs, never mid-stint.

## Every 5–10 laps

- Group laps by change (controls/setup/technique) and compare medians, not bests.
- Run `driver_lab.py coast` / `corner` on the group to confirm the drill is working (e.g. coast gap shrinking, re-steer falling).

## End of session

Run `driver_lab.py style` on the session's clean laps to update the driver profile, and `compare` for any setup or
controls change made during the session.

## Know when to stop

Fatigue shows as late-session over-slowing and repeated offs at a corner that was solved earlier (e.g. Turn 11 at 48 km/h
after four good laps). Recommend a break; lap times after ~3 hours rarely teach anything.

## Corrections

If a cue you gave caused a new problem (e.g. "brake 5 m later" → inside-front locks), say so plainly next lap and revert
to the previous cue.

**REQUIRED SUB-SKILL:** `vre-teach-answer`
