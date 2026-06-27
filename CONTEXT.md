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
- Skills: `vre-coach-router` → `vre-collect-evidence` → specialist → `vre-teach-answer`

Dynamics vocabulary: [docs/coach/dynamics-glossary.md](docs/coach/dynamics-glossary.md).
