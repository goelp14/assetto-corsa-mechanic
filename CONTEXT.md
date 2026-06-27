# Virtual Race Engineer — Domain Glossary

Ubiquitous language for telemetry coaching, aligned with `ac_app/config/telemetry_schema.json`.

## Core concepts

| Term | Meaning |
|------|---------|
| **Session** | One driving outing archived as `session.jsonl` + `laps/lap_NN.json` |
| **Bundle** | Exported replay folder under `exports/` for web viewer + coach agent |
| **Spline** | Normalized lap distance 0.0–1.0; primary X-axis for telemetry comparison |
| **Corner** | Track segment with id (e.g. `t7`), display name, spline_start/end |
| **Phase** | Corner sub-segment: `entry`, `mid`, `exit`, `straight` |
| **Reference lap** | Personal best sector phases in `sector_bests.json` — same car, same track, your data |
| **Incident** | Discrete loss-of-control event (beta spike) in `incidents.json` with pre-window |
| **Yaw gate** | Live/offline classification: `INTENTIONAL`, `LOSS_OF_CONTROL`, `NEUTRAL` |
| **Verdict** | `DRIVER_ERROR`, `SETUP_FLAW`, `INTENTIONAL`, `NONE` |
| **Drill** | One actionable fix for next session (max 1–2 per stint) |
| **Potential gap** | Time still on table vs stitched sector bests (`potential_gap_s`) |
| **Evidence pack** | Citation-tagged JSON for coach agent — no invented metrics |

## Coaching structure

Every coaching answer uses **WHAT / WHY / HOW**:

- **WHAT** — measured behaviour (speed, G, throttle, beta)
- **WHY** — vehicle dynamics mechanism (load transfer, grip envelope)
- **HOW** — one drill for next session

## Evidence sources

| File | Contents |
|------|----------|
| `analysis/incidents.json` | Spin/loss-of-control events |
| `analysis/corner_reports.json` | Root-cause investigations |
| `analysis/time_loss.json` | Ranked corner time loss |
| `analysis/session_plan.json` | Top drills |
| `analysis/annotations.json` | Viewer coaching pins |

## Coach agent

- CLI: `python -m external.query_tools.coach ask --bundle ... --question "..."`
- API: `POST /coach/ask` on port 8765 when `VRE_COACH=1` (via `./replay.sh`)
- Skills chain: `vre-coach-router` → `vre-collect-evidence` → specialist → `vre-teach-answer`

## Install & usage docs

- [docs/INSTALL.md](docs/INSTALL.md) — requirements, CM setup, troubleshooting
- [docs/USAGE.md](docs/USAGE.md) — replay viewer, CLI tools, setup workflow
