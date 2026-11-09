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
