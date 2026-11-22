# ACC rpy coaching evidence + Motec analysis LD — Implementation Plan

> **For agentic workers:** Execute task-by-task. Prefer TDD. Do **not** git commit unless the user asks.

**Goal:** Exact ACC coaching evidence from MoTeC (full channels) and `.rpy` (laps GO; validity/env/channels as unlocked), plus a Motec-openable `vre_analysis_*.ld` with VRE math overlays, and skills that forbid guessing.

**Architecture:** Expand MoTeC ingest to keep native-rate Epic channels; compute VRE derived series (coast, damper vel, rake proxy, yaw deg, US/OS, wheelspin); write analysis `.ld` via ldparser or a documented CSV+meta fallback if write API is insufficient. Parallel: decode rpy weather + search validity; update ACC skills to the evidence contract.

**Tech Stack:** Python 3, gotzl/ldparser, numpy, existing `acc_rpy` / `acc_ingest` / VRE skills.

**Spec:** `docs/superpowers/specs/2026-11-18-acc-rpy-coaching-evidence-design.md`

## Global Constraints

- No coaching claims from non-GO `.rpy` channels.
- Never truncate all MoTeC series to the shortest channel length; align by time/freq.
- EN_* pass-through only until named.
- Pace-first setup doctrine; no calm-only levers.
- User did not request git commits — skip commit steps.

---

### Task 1: Analysis maths module (pure functions)

**Files:**
- Create: `external/query_tools/acc_ingest/analysis_channels.py`
- Test: `external/query_tools/tests/test_acc_analysis_channels.py`

**Produces:** `coast_mask`, `damper_velocity`, `rake_proxy`, `yaw_rate_deg`, `us_os`, `wheelspin_lock` helpers.

- [x] Step 1–4: TDD for each helper with tiny synthetic arrays
- [x] Step 5: Skip commit

### Task 2: Full MoTeC channel load + TIME-reset laps (already partial)

**Files:**
- Modify: `external/query_tools/acc_ingest/motec_ld.py`
- Test: extend `external/query_tools/tests/test_acc_normalize.py` or new `test_motec_ld_time_splits.py`

**Produces:** `load_ld_channels(path) -> dict[str, ChannelSeries]` with freq + data; lap splits from TIME.

- [x] Keep SPEED→km/h conversion; expose SUS_TRAVEL, ROTY, etc.
- [x] Session import uses TIME ms exactly (already fixed)

### Task 3: Motec analysis `.ld` writer

**Files:**
- Create: `external/query_tools/acc_ingest/motec_analysis_ld.py`
- Test: `external/query_tools/tests/test_motec_analysis_ld.py`

**Produces:** `write_analysis_ld(out_path, channels, derived, meta) -> Path`

- [x] Prefer ldparser write; if impossible, write Motec-compatible channel CSV bundle + `analysis_meta.json` and document Motec import path
- [x] CLI: `python -m external.query_tools.acc_ingest.motec_analysis_ld Spa-....ld --out /tmp/vre_analysis_spa.ld --best-lap`

### Task 4: Rpy weather/env decode (raw → named where safe)

**Files:**
- Create: `external/query_tools/acc_rpy/env_decode.py`
- Modify: `processor.py` / `parse_rpy.py` to attach env to summary
- Test: `tests/test_acc_rpy_env.py`

- [x] env_decode + processor `env` block; names marked hypothesis

### Task 5: Validity search spike + document findings

**Files:**
- Create: `external/query_tools/acc_rpy/validity_scan.py`
- Spec note in `docs/superpowers/specs/acc-rpy-wire-from-exe.md`
- Test: fixture scan does not crash; records candidates

- [x] validity_scan candidates only; `RPY_VALIDITY_GO=false`

### Task 6: Skills update

**Files:**
- Modify: `~/.agents/skills/acc-rpy-re/SKILL.md` and repo copy if any
- Modify: `.agents/skills/vre-coach-router/SKILL.md`, `vre-collect-evidence`, `vre-acc-setup`

- [x] Evidence gates in acc-rpy-re, collect-evidence, coach-router, acc-setup, dampers

### Task 7: Ship analysis LD for user’s Spa MoTeC + Erik lap table

**Files:**
- Output under `/tmp/vre_analysis_spa/` or `exports/`
- Short coaching note using only GO Motec + Erik rpy lap times

- [x] `/tmp/vre_analysis_spa/` + COACHING.md + evidence pack
