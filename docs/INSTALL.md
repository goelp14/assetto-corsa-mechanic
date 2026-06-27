# Install

Setup for **Assetto Corsa + CSP**, **RSS Formula Hybrid X 2026**, and **Content Manager**.

---

## How it fits together

Two separate pieces — most users only need the first.

| Piece | Get it | Lives at |
|-------|--------|----------|
| **In-game app** | `VirtualRaceEngineer.zip` from [Releases](https://github.com/goelp14/assetto-corsa-mechanic/releases) | `<AC install>/apps/python/VirtualRaceEngineer/` |
| **Replay viewer** | Clone this repo, run `./replay.sh` | Repo folder on your PC |

```text
VirtualRaceEngineer.zip  →  Content Manager  →  …/assettocorsa/apps/python/VirtualRaceEngineer/
                                                      └── data/sessions/     ← laps saved here

Documents/Assetto Corsa/setups/rss_formula_hybrid_x_2026/<track>/Auto_Tweak.ini  ← load in pits

git clone + ./replay.sh  →  reads sessions  →  exports/  →  browser
```

### What's in the zip?

The in-game Python app only: coaching, setup writer, HUD, empty `data/` folders.

**Not in the zip:** replay viewer, `./replay.sh`, export scripts, lap data (created while you drive).

### Typical paths (Windows / Steam)

**App + telemetry:**

```text
C:\Program Files (x86)\Steam\steamapps\common\assettocorsa\
  apps\python\VirtualRaceEngineer\
    VirtualRaceEngineer.py
    data\sessions\<session_id>\session.jsonl
    data\sessions\<session_id>\laps\lap_05.json
```

**Setup files:**

```text
C:\Users\<you>\Documents\Assetto Corsa\setups\
  rss_formula_hybrid_x_2026\<track>\Auto_Tweak.ini
```

Override session location: `VRE_SESSIONS=/path/to/sessions`

---

## Path A — Drive only

1. Download **`VirtualRaceEngineer.zip`** → drag onto **Content Manager**
2. **Settings → Assetto Corsa → Apps** → enable Python apps → activate **Virtual Race Engineer**
3. Drive **RSS Formula Hybrid X 2026**, 2–3 clean laps (baseline learning)
4. Load **`Auto_Tweak.ini`** in pits when the ticker says a setup change is ready

No git clone required.

---

## Path B — Drive + replay

1. Complete **Path A**
2. `git clone https://github.com/goelp14/assetto-corsa-mechanic.git`
3. `chmod +x replay.sh` (once)
4. After each stint: `./replay.sh`

Requires **Python 3.10+** and **Node.js 18+** (first run builds the viewer).

See [USAGE.md](USAGE.md) for replay features and CLI tools.

---

## Path C — Developers

1. Clone repo → `./deploy/install.sh --open-cm` (copies `ac_app/` into the same AC folder as the zip)
2. Enable app in Content Manager (Path A step 2)
3. After edits: `./deploy/sync.sh` or `./deploy/install.sh --watch`

---

## Requirements

| Requirement | For |
|-------------|-----|
| AC + CSP + Content Manager | In-game app |
| RSS Formula Hybrid X 2026 | Target car |
| Git clone + Python 3.10+ + Node 18+ | Replay only |

---

## Optional: voice engineer (TTS)

Not in the zip. Speaks ticker messages aloud on Windows:

```bash
pip install -r external/tts_daemon/requirements.txt
python external/tts_daemon/engineer_voice.py --voice-file "C:/.../VirtualRaceEngineer/data/engineer_voice.txt"
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Where did the zip install? | `…/assettocorsa/apps/python/VirtualRaceEngineer/` |
| Where are my laps? | `…/VirtualRaceEngineer/data/sessions/` — drive with app enabled first |
| Where is Auto_Tweak? | `Documents/Assetto Corsa/setups/rss_formula_hybrid_x_2026/<track>/` |
| Replay finds no sessions | Complete a stint; run `./replay.sh` from git clone |
| App missing in CM | Re-install zip or `./deploy/install.sh`; restart CM |
| App errors | `Documents/Assetto Corsa/logs/py_log.txt` |
| Setup not applied | Load **Auto_Tweak.ini** in pits; save a baseline setup in that track folder first |
