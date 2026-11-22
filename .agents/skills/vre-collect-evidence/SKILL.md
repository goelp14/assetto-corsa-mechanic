---
name: vre-collect-evidence
description: Use when answering any VRE coaching question that needs session or replay bundle data.
---

# VRE Collect Evidence

Build the citation-tagged evidence pack before analysis.

## Steps

1. Ensure bundle exists under `exports/<session_id>/`
2. If missing or stale, run from repo root: `./replay.sh --force-sync` or `python external/query_tools/export_replay.py export <session_dir>`
3. Build pack:

```bash
python -m external.query_tools.coach pack \
  --bundle exports/<session_id> \
  --corner <id> --lap <n> --spline <0-1>
```

4. List `citation_ids` — every downstream claim must cite one

## Pack sections

- `incidents` — spins / high beta
- `corner_reports` — WHAT/WHY/HOW investigations
- `time_loss_corners` — ranked loss
- `session_plan.items` — drills
- `sample_window` — playhead-scoped samples

## ACC evidence gates (no guessing)

- **MoTeC `.ld`:** full native-rate channels via `acc_ingest.motec_analysis_ld.load_ld_channels`; never truncate all series to the shortest length. Analysis overlays: `python -m external.query_tools.acc_ingest.motec_analysis_ld FILE.ld --out /tmp/vre_analysis.ld`.
- **`.rpy` laps + validity:** GO (`extract_lap_times_ms`, `lap_validity` arr_24 flag — empirical).
- **`.rpy` inputs (arr_30):** GO — MoTeC gold 2026-11-21, aligned: SPEED 1.000, BRAKE 0.999, GEAR 0.999, RPMS 0.999, STEERANGLE 0.996 (steering-wheel °), THROTTLE 0.996, G_LAT 0.992, G_LON 0.986; unity scale, zero lag. Native rate 8–11 Hz (state it; ±5–7 m on braking points at 200 km/h).
- **`.rpy` pose (rec_68):** GO — car centre + 4 wheel contact points (true yaw, slip, edge margin), elevation. Pose clock ≠ input clock: fit the offset per file (Spa replays: +0.6 s), never assume it.
- **NO-GO in `.rpy`:** tyre pressure/air temp, SUS_TRAVEL mm, TC/ABS in-action (code-proved not packed). Named weather = hypothesis; raw `RPY_WEATHER_*` floats OK.
- Source of truth for lane status: `docs/superpowers/specs/acc-rpy-pedal-unlock-playbook.md`.
- EN_* Motec channels: pass-through only until named.

## Lap-compare evidence (required method)

Follow `docs/coach/telemetry-analysis-playbook.md` before writing advice:

1. Align on **distance** (Motec corrected distance and/or pose `dist_m` / spline) — never time overlays for technique claims.
2. Build **cumulative variance** vs reference; cite top cliffs (Δt and metre range).
3. For each cliff, export a **brake → next brake** window with: brake onset (m, V), peak brake, turn-in sync, minV (m vs apex), sustained FT≥95 distance, exit speeds at +100/+200/+400 m.
4. **Mask auto-blip** on THROTTLE (`brk>30` + downshift or 1-sample spike) before coast/overlap claims.
5. Prefer same-car reference; if gap ≫ 1 s, only coach the steepest variance cliffs.
6. Online refresh when stuck: Popometer patterns, SOLOX Compare 3Q, MoTeC variance — do not invent new “overlap” myths.

## Session-level evidence (no bundle needed)

For root cause, lines, potential and live coaching, read session laps directly:

```bash
python external/query_tools/driver_lab.py coast|corner|lines|sim -s <session> [-s ...] --min-lap <a> --max-lap <b>
python external/query_tools/driver_lab.py controls
```

- Filter laps by time to exclude spins/offs/out-laps; split groups at every controls or setup change.
- `VRE_SESSIONS` / `VRE_AC_ROOT` / `VRE_AC_CONTROLS` override default paths.
- Quote only numbers these commands print.

## Files

- [evidence_pack.py](../../external/query_tools/coach/evidence_pack.py)
- [coaching-rubric.md](../../docs/coach/coaching-rubric.md)
