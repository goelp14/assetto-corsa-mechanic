# Using Virtual Race Engineer

## Typical workflow

```
Drive (in-game VRE) → Load Auto_Tweak in pits if prompted → ./replay.sh → review & drill
```

1. **Learning phase** — first ~2 laps: app records baselines, minimal coaching.
2. **Coaching phase** — orange corrections (driver input) and cyan opportunities (unused grip/speed).
3. **Setup phase** — after repeated setup symptoms, micro-tweaks queue for the next pit stop.
4. **Replay** — export stint, compare laps, read corner drills, optional coach chat.

---

## In-game HUD

- **Ticker** — headline coaching (exit grip, kerb, shift timing, etc.).
- **Setup ready** — load `Auto_Tweak.ini` in the setup screen before going out.
- **Bootstrap** — on new tracks, Monaco/Monza/Spa get a few safe default tweaks (wings, brake bias) after clean laps.

Coaching distinguishes:

- **Driver error** — inputs while tyres are loaded (early throttle, sawing on kerbs).
- **Setup flaw** — clean inputs but persistent balance issues (requires multi-lap evidence).
- **Intentional rotation** — yaw within your normal aggressive style.

---

## Replay viewer

Start: `./replay.sh` (see [INSTALL.md](INSTALL.md)).

| Feature | How |
|---------|-----|
| Switch session | Header session dropdown |
| Best lap | Defaults to ★ fastest flying lap |
| Compare lap | Optional dashed overlay (second lap) |
| Map ↔ charts | **Select region** or Shift+drag on map → zoom both |
| Reset zoom | **Full lap** button |
| Coach notes | Sky-blue pins; toggle in layers panel |
| Narrative | Stint debrief markdown in bundle `analysis/narrative.md` |

Hard-refresh the browser after viewer updates (`Ctrl+Shift+R`).

---

## CLI tools

All commands from **repo root** unless noted.

### Export / list sessions

```bash
python external/query_tools/export_replay.py --list
python external/query_tools/export_replay.py latest
python external/query_tools/export_replay.py 2026-06-27_172058_523_monaco_2020
```

### Session query (JSONL)

```bash
python external/query_tools/session_query.py --sessions-dir "$VRE_SESSIONS"
```

### Stint analysis report

```bash
python external/query_tools/analyze_sessions.py
```

### Coach notes (persist feedback on replay)

```bash
python external/query_tools/coach_notes.py add \
  --bundle 2026-06-27_172058_523_monaco_2020 \
  --corner "Turn 1" --phase exit \
  --title "Wait for reload off kerb" \
  --action "No throttle until wheel load returns after right curb."

python external/query_tools/coach_notes.py list --bundle latest
python external/query_tools/coach_notes.py remove --bundle latest --id note_001
```

Re-run export or `./replay.sh` so `manifest.coach_notes` is set.

### Coach agent (optional)

```bash
python -m external.query_tools.coach ask \
  --bundle exports/2026-06-27_172058_523_monaco_2020 \
  --question "Why did I lose time at Swimming Pool on lap 5?"
```

With `VRE_COACH=1`, `./replay.sh` also serves `POST /coach/ask` for the in-viewer chat panel.

---

## Setup tweaks

| File | Role |
|------|------|
| `Auto_Tweak.ini` | Engineer output — **load this in pits** |
| `last.ini` | AC’s last loaded setup (fallback clone source) |
| Your named setups | Preferred clone source (newest mtime wins) |

Setup memory per track lives in:

`VirtualRaceEngineer/data/setup_memory/<track_id>.json`

Harmful tweaks are down-weighted; the app avoids oscillating the same parameter.

**Symptom → typical tweak** (see `ac_app/config/setup_symptom_map.json`):

- Entry push → `FRONT_BIAS`, wings
- Kerb unsettled → softer `DAMP_BUMP` / `DAMP_REBOUND` front
- Shift unsettling → `DIFF_PRELOAD`

---

## Session archive layout

In-game (and after deploy):

```
VirtualRaceEngineer/data/sessions/<session_id>/
├── session.jsonl       # events, lap summaries, setup changes
├── laps/lap_NN.json    # subsampled telemetry per lap
└── README.txt
```

Exported for viewer:

```
exports/<session_id>/
├── manifest.json
├── geometry.json
├── laps/
└── analysis/           # time_loss, incidents, narrative, coach_notes, …
```

---

## Development

```bash
pip install -e ".[dev]"
python3 -m pytest tests/ -q
```

Regenerate car setup catalog after a mod update:

```bash
pip install git+https://github.com/PhilippKosarev/acd.git
python tools/extract_setup_catalog.py --acd path/to/data.acd --out ac_app/config/car_rss_fh_x_2026.json
```

Domain glossary: [../CONTEXT.md](../CONTEXT.md). Coaching rubric: [coach/coaching-rubric.md](coach/coaching-rubric.md).
