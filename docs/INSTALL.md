# Install Virtual Race Engineer

Step-by-step setup for **Assetto Corsa + CSP**, **RSS Formula Hybrid X 2026**, and **Content Manager**.

## Requirements

| Requirement | Notes |
|-------------|--------|
| Assetto Corsa | Steam install |
| [Custom Shaders Patch](https://github.com/ac-custom-shaders-patch/acc-extension-config) | Python apps + extended telemetry |
| Content Manager | Enable and launch the app |
| RSS Formula Hybrid X 2026 | Car id: `rss_formula_hybrid_x_2026` |
| Python 3.3 (in-game) | Bundled with AC — app uses **stdlib only** in `ac_app/` |

**For replay viewer / dev tools (WSL or Linux):**

- Python **3.10+**
- **Node.js 18+** and npm (first `./replay.sh` builds the viewer once)
- Optional: `pip install -e ".[dev]"` for tests

---

## 1. Install the in-game app

### WSL (recommended for development)

From the repo root:

```bash
chmod +x deploy/install.sh replay.sh
./deploy/install.sh --open-cm
```

This copies `ac_app/` to:

`…/assettocorsa/apps/python/VirtualRaceEngineer`

and creates runtime data folders (sessions, setup memory, baselines, grip map).

**Options**

```bash
./deploy/install.sh --watch          # re-sync on every save (needs inotify-tools)
./deploy/install.sh --link           # Windows junction if repo is under /mnt/c/...
AC_ROOT="/mnt/d/Games/assettocorsa" ./deploy/install.sh
./deploy/sync.sh                     # quick re-copy after edits
```

### Windows PowerShell

```powershell
powershell -ExecutionPolicy Bypass -File deploy/install.ps1
```

Use `-Copy` to copy files instead of a junction. Use `-AcRoot "D:\Games\assettocorsa"` if Steam is not in the default path.

### Content Manager zip (no WSL)

```bash
./deploy/package.sh
```

Drag `dist/VirtualRaceEngineer.zip` onto Content Manager (**Content → Install**).

Or download a pre-built zip from **[GitHub Releases](https://github.com/goelp14/assetto-corsa-mechanic/releases)** (built automatically on version tags — see [RELEASE.md](RELEASE.md)).

---

## 2. Enable in Content Manager

1. **Settings → Assetto Corsa → Apps**
2. Check **Enable Python apps**
3. Under **Activated apps**, check **Virtual Race Engineer**
4. *(Dev)* **Custom Shaders Patch → Developer → Python Apps Debug** → **Reload automatically**

Launch any session from CM. The VRE ticker should appear in-game.

---

## 3. First drive checklist

1. Pick **RSS Formula Hybrid X 2026** on a track with a profile (Monaco, Monza, Spa, or generic).
2. Load your normal setup in the pits (or `last.ini` — AC’s last loaded setup).
3. Drive **2–3 clean laps** so the app learns your baseline.
4. When the ticker says a setup tweak is ready, load **`Auto_Tweak.ini`** in the pit setup screen.

Setup output path:

`Documents/Assetto Corsa/setups/rss_formula_hybrid_x_2026/<track>/Auto_Tweak.ini`

The engineer clones from your newest named `.ini` in that track folder (not a stale snapshot unless nothing else exists). Override with env var `VRE_BASE_SETUP=MyBaseline.ini` if needed.

---

## 4. Replay viewer (post-stint analysis)

After driving with VRE active:

```bash
./replay.sh
```

This syncs sessions from your AC install, exports new stints to `exports/`, and opens the browser viewer.

```bash
./replay.sh --force-sync    # re-export everything
./replay.sh --sync-only     # export without starting the server
./replay.sh --no-open       # server only
```

**First run:** installs and builds `replay-viewer/` automatically if `dist/` is missing.

**Session location (default):**

`…/apps/python/VirtualRaceEngineer/data/sessions/`

Override with `VRE_SESSIONS=/path/to/sessions`.

---

## 5. Optional: voice engineer (TTS)

Run from **Windows** Python (WSL audio is unreliable):

```bash
pip install -r external/tts_daemon/requirements.txt
python external/tts_daemon/engineer_voice.py --voice-file "path/to/VirtualRaceEngineer/data/engineer_voice.txt"
```

The in-game app writes one-line messages to `engineer_voice.txt`; the daemon speaks them.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| App not in CM list | Re-run `./deploy/install.sh`, restart CM |
| App errors on load | Check `Documents/Assetto Corsa/logs/py_log.txt` |
| No sessions in replay | Drive at least one stint with VRE enabled; check `VRE_SESSIONS` |
| Viewer build fails | `cd replay-viewer && npm install && npm run build` |
| Setup not applied | Load **Auto_Tweak.ini** in pits; ensure a base `.ini` exists in the track setup folder |
| `setup_apply_failed: no_output_ini` | No base setup in track folder — save a setup once in AC first |

---

## What gets gitignored (dev)

Runtime telemetry under `ac_app/data/` and exported bundles under `exports/` are not committed. Only `ac_app/data/track_geometry/` and placeholder `.gitkeep` files are tracked.

See [USAGE.md](USAGE.md) for day-to-day workflow and CLI tools.
