# Usage

Day-to-day workflow after [install](INSTALL.md).

---

## Workflow

```text
Drive (in-game VRE) → Load Auto_Tweak in pits if prompted → ./replay.sh → review & drill
```

1. **Learning** — first ~2 laps: baselines recorded, minimal coaching
2. **Coaching** — orange corrections (driver input), cyan opportunities (unused grip)
3. **Setup** — repeated setup symptoms queue micro-tweaks for next pit stop
4. **Replay** — export stint, compare laps, corner drills, optional coach chat

---

## In-game HUD

- **Ticker** — headline coaching (exit grip, kerb, shift timing, etc.)
- **Setup ready** — load `Auto_Tweak.ini` before going out
- **Bootstrap** — Monaco/Monza/Spa get safe default tweaks (wings, brake bias) after clean laps on new tracks

**Verdicts:** driver error (inputs while loaded), setup flaw (clean inputs, persistent balance), intentional rotation (yaw within your style).

---

## Replay viewer

```bash
./replay.sh                  # sync sessions + open browser
./replay.sh --force-sync     # re-export all sessions
./replay.sh --sync-only      # export only
```

Sessions are read from `<AC install>/apps/python/VirtualRaceEngineer/data/sessions/`. Exports land in `exports/` (gitignored). First run builds the viewer if needed.

| Feature | How |
|---------|-----|
| Switch session | Header dropdown |
| Best lap | Defaults to fastest flying lap |
| Compare lap | Optional dashed overlay |
| Map ↔ charts | **Select region** or Shift+drag → zoom both |
| Reset zoom | **Full lap** |
| Coach notes | Sky-blue pins; toggle in layers |
| Narrative | `exports/<id>/analysis/narrative.md` |

Hard-refresh after viewer updates (`Ctrl+Shift+R`).

Optional coach chat: set `VRE_COACH=1` when running `./replay.sh`.

---

## Setup tweaks

| File | Role |
|------|------|
| `Auto_Tweak.ini` | Engineer output — **load in pits** |
| `last.ini` | AC fallback clone source |
| Your named setups | Preferred clone source (newest mtime) |

Memory per track: `VirtualRaceEngineer/data/setup_memory/<track_id>.json`

Pin a base setup: `VRE_BASE_SETUP=MyBaseline.ini`

**Symptom → typical tweak** (`ac_app/config/setup_symptom_map.json`):

- Entry push → `FRONT_BIAS`, wings
- Kerb unsettled → softer `DAMP_BUMP` / `DAMP_REBOUND` front
- Shift unsettling → `DIFF_PRELOAD`

---

## CLI tools

From repo root.

**Export / list:**

```bash
python external/query_tools/export_replay.py --list
python external/query_tools/export_replay.py latest
python external/query_tools/export_replay.py <session_id>
```

**Stint analysis:**

```bash
python external/query_tools/analyze_sessions.py
```

**Coach notes** (persist on replay bundles):

```bash
python external/query_tools/coach_notes.py add \
  --bundle <session_id> --corner "Turn 1" --phase exit \
  --title "Wait for reload off kerb" \
  --action "No throttle until wheel load returns."

python external/query_tools/coach_notes.py list --bundle latest
```

Re-run `./replay.sh` after adding notes.

**Coach agent:**

```bash
python -m external.query_tools.coach ask \
  --bundle exports/<session_id> \
  --question "Why did I lose time at Swimming Pool on lap 5?"
```

---

## Session layout

**In-game:**

```text
VirtualRaceEngineer/data/sessions/<session_id>/
├── session.jsonl
├── laps/lap_NN.json
└── README.txt
```

**Exported:**

```text
exports/<session_id>/
├── manifest.json
├── geometry.json
├── laps/
└── analysis/          # time_loss, incidents, narrative, coach_notes, …
```

---

## Development

```bash
pip install -e ".[dev]"
python3 -m pytest tests/ -q
./deploy/install.sh --watch    # live sync while editing ac_app/
./deploy/sync.sh               # one-shot redeploy
```

Add a car (or regenerate one) from its `data.acd`, no extra packages needed:

```bash
python tools/extract_car_profile.py ks_ferrari_312_67     # writes ac_app/config/cars/<car_id>.json
```

Add a track layout from its AI line (corners come from where the AI slows down; check the `--dry-run` list, then name them):

```bash
python tools/build_track_config.py rt_sonoma --layout long --dry-run
python tools/build_track_config.py rt_sonoma --layout long --names "Turn 2,Turn 3,..."
python external/query_tools/build_track_geometry.py --track rt_sonoma-long   # replay map
```

Cars without a profile still get driving coaching, but no setup changes. Tracks without a `config/tracks/<track>-<layout>.json` get coaching without named corners. Learned data (baselines, phase, line references) is stored per car and layout.

Replay viewer dev server: `cd replay-viewer && npm run dev` (serve bundles via `./replay.sh`).

---

## Coach agent reference

Domain terms: [CONTEXT.md](../CONTEXT.md). Coaching rules: [docs/coach/](coach/). Skills: [`.agents/skills/`](../.agents/skills/README.md).
