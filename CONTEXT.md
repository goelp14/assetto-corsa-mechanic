# Domain Glossary

Ubiquitous language for telemetry coaching. Aligned with `ac_app/config/telemetry_schema.json`.  
**Read by coach agent skills** (`vre-*` in `.agents/skills/`).

## Core concepts

| Term | Meaning |
|------|---------|
| **Session** | One outing: `session.jsonl` + `laps/lap_NN.json` |
| **Bundle** | Exported replay folder under `exports/` |
| **Spline** | Normalized lap distance 0.0–1.0 |
| **Corner** | Track segment with id (e.g. `t7`), display name, spline range |
| **Phase** | `entry`, `mid`, `exit`, `straight` |
| **Reference lap** | Personal sector bests in `sector_bests.json` |
| **Incident** | Loss-of-control event in `incidents.json` |
| **Yaw gate** | `INTENTIONAL`, `LOSS_OF_CONTROL`, `NEUTRAL` |
| **Verdict** | `DRIVER_ERROR`, `SETUP_FLAW`, `INTENTIONAL`, `NONE` |
| **Drill** | One actionable fix for next session (max 1–2 per stint) |
| **Potential gap** | Time vs stitched sector bests (`potential_gap_s`) |
| **Evidence pack** | Citation-tagged JSON for coach — no invented metrics |

## Coaching structure

Every answer: **WHAT** (measured behaviour) / **WHY** (mechanism) / **HOW** (one drill).

See [docs/coach/coaching-rubric.md](docs/coach/coaching-rubric.md) and [docs/coach/pedagogy.md](docs/coach/pedagogy.md).

## Evidence sources

| File | Contents |
|------|----------|
| `analysis/incidents.json` | Spin / loss-of-control |
| `analysis/corner_reports.json` | Root-cause investigations |
| `analysis/time_loss.json` | Ranked corner time loss |
| `analysis/session_plan.json` | Top drills |
| `analysis/annotations.json` | Viewer coaching pins |

## Coach agent

- CLI: `python -m external.query_tools.coach ask --bundle exports/<id> --question "..."`
- API: `POST /coach/ask` on port 8765 when `VRE_COACH=1`
- Skills: `vre-coach-router` → evidence (`vre-collect-evidence` or `driver_lab.py`) → specialist → `vre-teach-answer`
- Session analysis CLI: `python external/query_tools/driver_lab.py {controls,coast,corner,lines,sim,compare,style}`

## Analysis terms

| Term | Meaning |
|------|---------|
| **Pass** | One car's trip through one corner on one lap |
| **Fast/slow quarter** | Fastest/slowest 25% of passes through a corner by section time |
| **Coast (while turning)** | Brake < 5% and throttle < 5% with steering; classified A save / B rotation wait / C pedal swap / D lift |
| **Pedal gap** | Brake-off → throttle-on time; the most common upstream cause of late throttle |
| **Re-steer** | Steering added after the apex — car not pointed |
| **Station** | Fixed track-metre point used to compare passes (10–20 m apart) |
| **Transition loss** | Real median lap − sim at the same grip |
| **Driver profile** | `ac_app/data/driver_profile.json`: per-session style metrics, labels, stated preferences |
| **Pace-first verdict** | A setup change is good only if it is faster (or equal and preferred); stable-but-slower fails |

Dynamics vocabulary: [docs/coach/dynamics-glossary.md](docs/coach/dynamics-glossary.md).
