# Virtual Race Engineer

[![CI](https://github.com/goelp14/assetto-corsa-mechanic/actions/workflows/ci.yml/badge.svg)](https://github.com/goelp14/assetto-corsa-mechanic/actions/workflows/ci.yml)

In-game **Assetto Corsa** coach and setup engineer. Learns your baseline per car and track layout, separates driver error from setup flaws, writes setup tweaks, and archives telemetry for offline replay.

Setup profiles ship for the **RSS Formula Hybrid X 2026** and **Ferrari 312/67**; add any other car with `tools/extract_car_profile.py` (see [docs/USAGE.md](docs/USAGE.md)). Named-corner configs ship for Monaco, Monza and Sonoma (Long).

**Requires:** Assetto Corsa, **CSP**, **Content Manager**.

---

## Quick start

| Step | Action |
|------|--------|
| **Install** | Download [`VirtualRaceEngineer.zip`](https://github.com/goelp14/assetto-corsa-mechanic/releases) → drag onto **Content Manager** → enable under Settings → Assetto Corsa → Apps |
| **Drive** | Load `Auto_Tweak.ini` in pits when the ticker prompts (`Documents/Assetto Corsa/setups/rss_formula_hybrid_x_2026/<track>/`) |
| **Replay** *(optional)* | Clone this repo → `./replay.sh` — **not included in the zip** |

| **ACC Lap Studio** *(optional)* | `pip install -e .[acc]` → `./replay.sh --rpy mine.rpy:You --ref faster.rpy:Ref` |

**ACC Lap Studio** turns two ACC replays (any car, any track) into a frame-accurate side-by-side review: both cars on the
map at their real position and heading, linked telemetry with a time-delta lane, corner-by-corner breakdown with braking
points described in driver language ("you reach full brake 7 car lengths after the reference"), coaching fixes for habits
and wrong mental models, track-limit verdicts, a setup read-out measured from the car's behaviour, and coach-style video
reviews that an AI can write and drive through the viewer MCP server (`external/query_tools/viewer_mcp.py`).

**[Install guide](docs/INSTALL.md)** — where the zip goes, where laps are saved, zip vs git clone.  
**[Usage guide](docs/USAGE.md)** — HUD, replay viewer, CLI tools, development.

---

## Documentation

| Doc | Audience |
|-----|----------|
| [docs/INSTALL.md](docs/INSTALL.md) | Install paths A/B/C, file locations, troubleshooting |
| [docs/USAGE.md](docs/USAGE.md) | Day-to-day workflow, replay, CLI, setup tweaks, dev commands |
| [docs/RELEASE.md](docs/RELEASE.md) | Cutting releases, CI (maintainers) |
| [CONTEXT.md](CONTEXT.md) | Domain glossary — used by coach agent skills |
| [docs/coach/](docs/coach/) | Coaching rubric, pedagogy, dynamics — used by coach agent skills |
| [SECURITY.md](SECURITY.md) | Security policy |

Coach agent skills live in [`.agents/skills/`](.agents/skills/README.md) (`vre-*`).
