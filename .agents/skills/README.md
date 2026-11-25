# Coach agent skills

Committed skills for telemetry coaching in this repo. Car- and track-agnostic.

| Skill | Game | Role |
|-------|------|------|
| `vre-coach-router` | both | Entry point: ground rules, game scope, data sources, routing |
| `vre-collect-evidence` | both (+ ACC `.rpy` gates) | Evidence from replay bundles or session laps |
| `vre-acc-replay-analysis` | ACC | `.rpy` → Lap Studio bundle: frames, corners, limits, setup read-out, coaching |
| `vre-video-review` | both | Coach-style video review in Lap Studio; AI drives the viewer (MCP), grounded reviews |
| `vre-root-cause` | both | Trace exits/hesitation/coasting back to the upstream cause |
| `vre-line-analysis` | both | Edge-independent line study on the driver's own passes |
| `vre-coaching-session` | both | Run a session like a coach: watch → reference → 1–2 mechanisms → drill/homework → retest |
| `vre-corner-coaching` | both | One drill + driver-language cues; rotation model (MRP, closing spiral, grip gap) |
| `vre-incident-analysis` | both | Spins / loss-of-control |
| `vre-explain-dynamics` | both | Physics / mechanism (elevation, braking balance, load transfer) |
| `vre-car-research` | both | What is universal vs car-specific; how to research and store car facts |
| `vre-setup-and-controls` | AC | Controls check, pace-first setup changes, A/B protocol |
| `vre-dampers` | AC (physics: both) | Damper physics, velocity histograms, damper A/B tests |
| `vre-acc-setup` | ACC | GT3 garage setup — pace-first, post-1.9; setup read-out from replays |
| `vre-acc-tyres` | ACC | Tyre pressures, temps, graining |
| `vre-acc-electronics` | ACC | TC1/TC2, ABS, ECU maps |
| `vre-driver-profile` | both | Persistent driving-style profile, habits across tracks/cars, preferences |
| `vre-pace-potential` | both | Achievable lap time, alien gap, style comparisons |
| `vre-live-session` | AC/VRE live | Lap-by-lap coaching while the driver is on track |
| `vre-teach-answer` | both | Final driver-facing response |
| `vre-annotate-replay` | both | Persist notes on replay bundles (classic + Lap Studio) |
| `motec-mt2-workspace` | ACC exports | MoTeC workspace, VRE pose channels, export verify |

**ACC replays → Lap Studio:** `./replay.sh --rpy me.rpy:You --ref fast.rpy:Ref` (bundle: `external/query_tools/acc_replay_bundle.py`;
coaching: `coach/acc_coach.py` → habits, fixes, diagnosis, landmarks; reviews: `coach/reviews.py`; viewer MCP: `viewer_mcp.py`).

**Analysis CLI:** `python external/query_tools/driver_lab.py {controls,coast,corner,lines,sim,compare,style,dampers}`.

**ACC ingest:** `external/query_tools/acc_ingest/` (shared-memory logger + Motec helpers).  
**ACC .rpy → Motec CLI (public):** https://github.com/goelp14/vre-rpy-cli

**Reference docs:** [CONTEXT.md](../../CONTEXT.md), [docs/coach/](../../docs/coach/), [docs/superpowers/specs/acc-ingest.md](../../docs/superpowers/specs/acc-ingest.md).

Other skills installed locally via `npx skills` are gitignored.
