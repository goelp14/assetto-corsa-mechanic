# Virtual Race Engineer

[![CI](https://github.com/goelp14/assetto-corsa-mechanic/actions/workflows/ci.yml/badge.svg)](https://github.com/goelp14/assetto-corsa-mechanic/actions/workflows/ci.yml)

In-game **Assetto Corsa** coach and setup engineer for **RSS Formula Hybrid X 2026**. Learns your baseline, separates driver error from setup flaws, writes setup tweaks, and archives telemetry for offline replay.

**Requires:** Assetto Corsa, **CSP**, **Content Manager**, RSS FH X 2026.

---

## Quick start

| Step | Action |
|------|--------|
| **Install** | Download [`VirtualRaceEngineer.zip`](https://github.com/goelp14/assetto-corsa-mechanic/releases) → drag onto **Content Manager** → enable under Settings → Assetto Corsa → Apps |
| **Drive** | Load `Auto_Tweak.ini` in pits when the ticker prompts (`Documents/Assetto Corsa/setups/rss_formula_hybrid_x_2026/<track>/`) |
| **Replay** *(optional)* | Clone this repo → `./replay.sh` — **not included in the zip** |

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
