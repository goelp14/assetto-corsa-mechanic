---
name: vre-video-review
description: Use when the user wants to be shown (not just told) what they did right or wrong in a replay — coach-style video review, corner breakdowns, annotations on the map/traces, or when the Lap Studio viewer is open and the AI should drive it.
---

# VRE Video Review (Lap Studio)

**Scope: cross-game method; runs on Lap Studio bundles (ACC replays today, any bundle with frames tomorrow).**

## Tools

MCP server (stdio): `claude mcp add vre-viewer -- python3 external/query_tools/viewer_mcp.py --url http://127.0.0.1:8765`
(launcher must be running: `./replay.sh`). Without MCP, the same API: `POST /api/viewer/command {"cmd", "args"}`,
`GET /api/viewer/state`, `POST /api/bundles/<id>/reviews/<name>`, `POST /api/bundles/<id>/annotations`.

| Read | Drive | Draw / author |
|---|---|---|
| `get_state` (what's on screen, both cars' values, apex-relative "where") | `focus_corner(corner, play)` | `annotate([{kind, at_m, s0_m, s1_m, driver, text}], persist)` |
| `get_coaching` | `play_range(s0, s1, rate, mode)` | `add_scene` (draft in the editor) |
| `get_corner(corner)` → events, landmarks, terrain, **citation paths** | `seek`, `pause`, `set_mode` | `create_review(name, {title, scenes})` |
| `get_frames_window(s0, s1)` | `set_laps(me, ref)`, `set_tab`, `set_map_color` | `open_review(name, scene)` |

## How a coach runs a review

1. **Pick 1–3 scenes** from `get_coaching` fixes (biggest repeatable time), plus one strength so the driver keeps it.
2. Per scene, `get_corner` → frame from ~70 m before the first braking point to ~200 m past the apex.
3. **Same place** (`mode: "dist"`) to compare inputs metre by metre; **same moment** (`"time"`) to *show* the gap opening.
   Rate 0.25–0.5 through braking, 1× on exits.
4. **Pauses at the decisive frames:** brake onset, full pressure, release, turn-in, slowest point, full throttle. Each pause
   says one thing in driver language from `coaching.landmarks` ("Erik reaches full brake 7 car lengths earlier").
5. Overlays: a `zone` between the two braking points, a `pin` where the reference is back on throttle, a crest/dip pin
   when terrain explains it.
6. End the scene with the drill + success metric from the fix.

## Grounding rule (enforced)

Every number in narration, pauses and overlay text must appear in a cited object (rounding allowed at the precision you
write). Cite the paths `get_corner` returns (`analysis.drivers.<d>.corners.<key>.best_lap`, `coaching.landmarks.<key>`,
`coaching.fixes.<i>`, `analysis.corner_loss_best_vs_ref.<i>`). The server returns 422 with the exact offending number —
fix the text, never the citation. Counts below 3 ("two fixes") are exempt; words like "a car length" are free.

## Live annotations while talking

When answering in chat while the viewer is open: `focus_corner`, then `annotate` the 1–2 points you are describing
(`persist: false`), so the driver sees exactly where. Persist only notes they will revisit (`vre-annotate-replay`).

**REQUIRED SUB-SKILL:** `vre-teach-answer` (same pedagogy: one or two fixes, visual cues, pace first).
