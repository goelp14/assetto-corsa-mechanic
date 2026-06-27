---
name: vre-annotate-replay
description: Use after giving lap- or corner-specific coaching feedback so notes persist on the replay map and telemetry charts.
---

# VRE Annotate Replay

When you discuss **specific laps and corners** with the user, persist the feedback so it appears in the replay viewer on next boot.

## When to annotate

- You identified time loss, technique issue, or drill at a **specific lap + corner**
- User asked for feedback they will revisit in the replay viewer
- Do **not** annotate generic stint summaries with no lap/corner anchor

## Workflow

1. Resolve bundle: `exports/<session_id>/` (run `./replay.sh` if missing)
2. Add one note per distinct coaching point:

```bash
python external/query_tools/coach_notes.py add \
  -b exports/<session_id> \
  -l <lap> \
  -c "<corner name or display name>" \
  -t "<short title>" \
  --what "<observed behavior>" \
  --why "<mechanism / cause>" \
  --action "<drill for next session>"
```

3. Confirm: `python external/query_tools/coach_notes.py list -b exports/<session_id>`

## Corner names

Use track config names (`Final Corner`, `Tabac`) or display names (`Anthony Noghes`). The tool resolves either.

## Viewer behavior

Notes load from `analysis/coach_notes.json`, show as **sky-blue pins** on the map, shaded regions on charts, and in the **Coach notes** sidebar list. Toggle with **Coach notes** in Layers.

Re-exporting a session does **not** wipe coach notes.
