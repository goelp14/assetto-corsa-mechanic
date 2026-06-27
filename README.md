# Virtual Race Engineer

In-game **Assetto Corsa** coach and setup engineer for the **RSS Formula Hybrid X 2026** (`rss_formula_hybrid_x_2026`). Learns your driving baseline, separates driver error from setup flaws, writes self-calibrating setup tweaks, and archives session telemetry for offline replay and analysis.

**Requires:** Assetto Corsa, **CSP**, **Content Manager**, embedded **Python 3.3** (in-game app is stdlib-only).

---

## Quick start

### 1. Install the app

**WSL / Linux (dev):**

```bash
chmod +x deploy/install.sh replay.sh
./deploy/install.sh --open-cm
```

**Windows:** `powershell -ExecutionPolicy Bypass -File deploy/install.ps1`

**Content Manager zip:** `./deploy/package.sh` → drag `dist/VirtualRaceEngineer.zip` onto CM.

Full details: **[docs/INSTALL.md](docs/INSTALL.md)**

### 2. Enable in Content Manager

Settings → Assetto Corsa → Apps → **Enable Python apps** → activate **Virtual Race Engineer**.

### 3. Drive, then review

- In pits: load **`Auto_Tweak.ini`** when the ticker says a setup change is ready.
- After the stint: **`./replay.sh`** — syncs sessions and opens the replay viewer in your browser.

Day-to-day workflow: **[docs/USAGE.md](docs/USAGE.md)**

---

## What it does

| Capability | Description |
|------------|-------------|
| **Learning phase** | Per-corner input baselines before coaching |
| **Three-way classifier** | Driver error vs setup flaw vs intentional rotation |
| **Actionable feedback** | On-screen ticker + optional [TTS daemon](external/tts_daemon/) |
| **Setup memory** | Tracks tweak effectiveness; avoids harmful oscillation |
| **Full lever catalog** | 77 setup sections from the car's `setup.ini` |
| **Telemetry archive** | JSONL sessions + per-lap JSON |
| **Replay viewer** | Map, telemetry, time loss, coach notes, optional AI coach |

---

## Replay viewer

```bash
./replay.sh                  # sync + open browser (default)
./replay.sh --force-sync       # re-export all sessions
./replay.sh --sync-only        # export only, no server
```

Sessions are read from your AC install (`VirtualRaceEngineer/data/sessions/`). Exports land in `exports/` (gitignored).

First run builds the viewer (`npm install && npm run build`) if needed — requires **Node.js 18+**.

---

## Project layout

| Path | Purpose |
|------|---------|
| `ac_app/` | In-game Python app (`VirtualRaceEngineer.py`, `lib/`, `config/`) |
| `ac_app/data/track_geometry/` | Pre-built track maps (committed) |
| `ac_app/data/sessions/` | Runtime telemetry (gitignored; `.gitkeep` only) |
| `deploy/` | `install.sh`, `install.ps1`, `package.sh`, `sync.sh` |
| `external/query_tools/` | Export, analysis, coach CLI |
| `external/tts_daemon/` | Optional voice engineer |
| `replay-viewer/` | React post-stint viewer |
| `exports/` | Exported replay bundles (gitignored) |
| `docs/` | Install, usage, coaching docs |
| `tests/` | pytest suite |

---

## Development

```bash
pip install -e ".[dev]"
python3 -m pytest tests/ -q
```

```bash
./deploy/install.sh --watch    # live sync while editing ac_app/
./deploy/sync.sh               # one-shot redeploy
```

Regenerate setup catalog after unpacking the car's `data.acd`:

```bash
pip install git+https://github.com/PhilippKosarev/acd.git
python tools/extract_setup_catalog.py --acd path/to/data.acd --out ac_app/config/car_rss_fh_x_2026.json
```

---

## Setup output

`Documents/Assetto Corsa/setups/rss_formula_hybrid_x_2026/<track>/Auto_Tweak.ini`

Cloned from your newest named setup in that track folder. Set `VRE_BASE_SETUP=MyBaseline.ini` to pin a specific base.

---

## Docs

- [Install guide](docs/INSTALL.md)
- [Usage & CLI tools](docs/USAGE.md)
- [Domain glossary](CONTEXT.md)
- [Replay viewer UX notes](docs/replay-viewer-driver-learning-ux.md)
- [Coaching rubric](docs/coach/coaching-rubric.md)

---

## Session archive (example)

```
VirtualRaceEngineer/data/sessions/2026-06-27_172058_523_monaco_2020/
├── session.jsonl
├── laps/lap_05.json
└── README.txt
```

---

## License

See repository license file if present.
