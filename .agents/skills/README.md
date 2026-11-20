# Coach agent skills

Committed skills for telemetry coaching in this repo. Car- and track-agnostic.

| Skill | Role |
|-------|------|
| `vre-coach-router` | Entry point: ground rules, data sources, routing |
| `vre-collect-evidence` | Evidence from replay bundles or session laps |
| `vre-root-cause` | Trace exits/hesitation/coasting back to the upstream cause |
| `vre-line-analysis` | Edge-independent line study on the driver's own passes |
| `vre-corner-coaching` | One drill + visual cues per corner |
| `vre-incident-analysis` | Spins / loss-of-control |
| `vre-explain-dynamics` | Physics / mechanism (incl. elevation) |
| `vre-setup-and-controls` | Controls check, pace-first setup changes, A/B protocol (AC) |
| `vre-acc-setup` | ACC GT3 garage setup — pace-first, post-1.9 physics |
| `vre-acc-tyres` | ACC tyre pressures, temps, graining |
| `vre-acc-electronics` | ACC TC1/TC2, ABS, ECU maps |
| `vre-dampers` | Damper physics (damping ratios, transient balance), velocity histograms, damper A/B tests |
| `vre-driver-profile` | Persistent driving-style profile and preferences |
| `vre-pace-potential` | Achievable lap time, alien gap, style comparisons |
| `vre-live-session` | Lap-by-lap coaching while the driver is on track |
| `vre-teach-answer` | Final driver-facing response |
| `vre-annotate-replay` | Persist notes on replay bundles |
| `motec-mt2-workspace` | Motec Track Map / Corr Dist / Internal Maths SPEED / export verify |

**Analysis CLI:** `python external/query_tools/driver_lab.py {controls,coast,corner,lines,sim,compare,style,dampers}`.

**ACC ingest:** `external/query_tools/acc_ingest/` (shared-memory logger + Motec helpers).  
**ACC .rpy → Motec CLI (public):** https://github.com/goelp14/vre-rpy-cli

**Reference docs:** [CONTEXT.md](../../CONTEXT.md), [docs/coach/](../../docs/coach/), [docs/superpowers/specs/acc-ingest.md](../../docs/superpowers/specs/acc-ingest.md).

Other skills installed locally via `npx skills` are gitignored.
