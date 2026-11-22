# ACC replay coaching: decoder → habits → distilled advice → visual replay — Implementation Plan

> **For agentic workers:** Execute phase-by-phase. Prefer TDD. Do **not** git commit unless the user asks.
> Before any decoder or Ghidra work read `docs/superpowers/specs/acc-rpy-pedal-unlock-playbook.md`
> (incl. "Review 2026-11-21") and the skills `acc-rpy-re`, `decomp-first-stream-re`, `ghidra-ida-re`.

**Goal:** From any ACC `.rpy` pair (yours + a reference), for **any car and any track**:
1. decode everything the replay holds, correctly and fully;
2. measure your habits and tendencies, good and bad, against the reference and your own laps;
3. keep a driver profile so advice works with your current style;
4. distil it into 1–2 pace-first fixes that correct wrong mental models, explained with track physics (elevation, load,
   traction);
5. show it in the viewer as a side-by-side, frame-by-frame replay with the advice pinned to exact metres.

**Prototype (approved direction, one corner only):** https://claude.ai/artifact/GtRFvNnp5eU9s9TbGRo76s

**Repos and ownership**

| Layer | Lives in | Why |
|-------|----------|-----|
| Decoder, clocks, frames, track packs, generic per-lap metrics | `~/github/vre-rpy-cli` (`vre_rpy`, **public**) | User: CLI is the current version; all decoder/CLI fixes go here |
| RE notes, addresses, Ghidra scripts/outputs, fixtures | this repo `docs/superpowers/` (private) | `PUBLISH.md`: never commit RE notes/addresses, personal paths or real-driver fixtures to the CLI |
| Habits, profile, coaching distiller, skills, viewer | this repo | Coaching product |

`external/query_tools/acc_rpy` is currently a duplicate of `vre_rpy` (same logic, unscrubbed comments). Phase 0 makes
this repo import `vre_rpy` so there is one decoder.

---

## Audit (2026-11-21)

| # | Layer | Finding | Severity | Phase |
|---|-------|---------|----------|-------|
| A1 | Analysis | ACC bundles show impossible KPIs: best lap 70.093 s at Spa (partial lap counted), theoretical best 0.924 s / "69.169 s on the table", theoretical best **slower** than best lap (155.8 vs 146.8 s). Cause: `LapTimeAnalyzer` stitches the *max single-sample speed* per 19 m bucket and skips empty buckets; ACC MoTeC-ingested laps have 400 samples/lap (~2.7 Hz), so most buckets are empty. No sanity gate. | critical | 3 |
| A2 | Analysis | Every recent ACC bundle has 0 corner reports, 0 incidents, empty session plan; only hand-written coach notes carry content. | critical | 3–5 |
| A3 | Analysis | `driver_lab.py` (style/profile/corner/lines) is AC-only: reads AC `fast_lane.ai` from the AC install; assumes steer > 0 = right (ACC replays: negative = right). Profile has no ACC entries and no reference comparison. | high | 4 |
| A4 | Decode | arr_30 velocity vector, vertical G, drivetrain speed and flag bits were packed but never decoded (packer decomp already existed). | high | 1 |
| A5 | Decode | rec_68 wheel points (true yaw, slip, edge margin) and hdr16 tyre radii unused; wheel speed uses a fixed 0.337 m radius. | high | 1 |
| A6 | Decode | Pose/input clocks differ by ~0.6 s; nothing fits it. Lap matcher off by one when a replay starts mid-lap (loses Erik's 2:15.425). Exports thin pose to 8000 points/session and draw lap 0 as "the line". | high | 1 |
| A7 | Decode | MP replays fail to parse (leaderboard section) → can't use any car from a race as reference. | medium | 1b |
| A8 | Track | Only Spa/Monza(+Imola) configs in this repo; CLI has 20 track packs. Spa corner windows are hand-drawn and span several turns; La Source and Fagnes directions were wrong (**fixed**). Hard-coded Spa/Monza lengths and lookups in `pose_track`, `motec_ld`, `mt2_sections`, `rpy_motec_ld`. Steering lock 400° defaulted everywhere. | high | 2 |
| A9 | Docs/skills | Coach skills told agents not to cite `.rpy` inputs although they match MoTeC at r ≥ 0.986; docstring r values 0.77–0.93 were alignment-limited (**fixed**, playbook updated). Global copies under `~/.agents/skills/` may still be stale. | medium | 0 |
| A10 | Tests | 2 collection errors (bare imports) + 2 stale NO-GO assertions (**fixed**: 211 passed, 4 skipped). `vre-rpy-cli` has **no tests**. | medium | 0 |
| A11 | Viewer | KPI strip/time-loss render A1's garbage without a warning; playhead and pins sit on the centreline, not the car; rpy export bundles aren't loadable. | high | 6 |
| A12 | MoTeC | `VRE_YAW_DEG` is all zeros in every export (needs a heading the decoded inputs don't have). | high | 1c |
| A13 | MoTeC | `VRE_ABS_ACT` precision 0.22 (flags ABS 4.5× too often); `VRE_TC_ACT` recall 0.22 (misses 78 % of TC). Exported as if they were state. | high | 1c |
| A14 | MoTeC | No position, elevation, slip angle, wheel/edge, lap-distance, validity, predicted-lap or corner channels; `VRE_DIST_M` is a drifting speed integral; `VRE_US_OS` uses a fixed 400° lock; wheel speed uses a fixed 0.337 m radius; pose (26.7/14.4 Hz) never reaches the `.ld`. | high | 1c |

## Unused data streams found (2026-11-21)

All code-backed from the existing packer decomp (`arr48_append.c`) and filler asm; details in the playbook.

| Stream | Source | Status | Use |
|--------|--------|--------|-----|
| World velocity vector (m/s) | arr_30 +16/+18/+20 | **GO** (\|v\| vs speed r 0.9999995) | true slip angle, vertical speed |
| Vertical G | arr_30 +26 | **GO** (r 0.89 vs d(v_y)/dt) | crests, dips, kerb strikes, load changes |
| 4 wheel contact points | rec_68 [5:17] | **GO** | yaw, body slip, wheel-to-edge margin, kerb use, real footprint |
| Elevation | rec_68 y | **GO** | gradient, vertical curvature → terrain features |
| Tyre radii F/R | hdr16 | **GO** | correct wheel speed / slip per car |
| ACC predicted lap time | arr_24 +4 | **GO (empirical)** | the in-game delta the driver saw |
| Drivetrain speed | arr_30 +22 (`0x558`) | hypothesis-named | clutch slip, shift quality |
| Flag bits | arr_30 +32 bit0, bits 1–4 | unknown | — |
| 5 cumulative counters | arr_10 bytes 0–4 (0.1 Hz) | hypothesis (`carDamage[5]` or wear) | damage/wear tracking once verified |
| Brake-phase quantity | arr_48 +60 (`Car+0x1420`) | unknown (not ABS) | — |
| Wheel slip accumulator | arr_48 +24 (`0x564`) | unknown | — |
| Not packed (code-proved) | — | NO-GO | tyre pressure/air temp, SUS mm, TC/ABS active, angular velocity |

## Global constraints

- **Car- and track-agnostic.** No track/car constants in code. Geometry from `fastlane.ai`; car dimensions/radii from the
  replay itself; steering lock and doctrine from per-car config with a "unknown car" path that still works.
  Every phase is verified on ≥ 3 tracks (Spa, Monza, Imola — single-player fixtures exist) and ≥ 1 non-296 car if a
  replay is available.
- **Evidence contract.** Only GO lanes; every number in advice comes from computed data; native sample rates shown.
  Sync is fitted and gated (speed-match r ≥ 0.98, else position-only).
- **Pace first.** A habit is "bad" only if it costs time (vs reference and/or own-lap correlation); "smoother/calmer" is
  never a goal. Advice extends the driver's natural style.
- **Pedagogy.** ≤ 2 fixes per session, one per corner; outside the tried range = "hypothesis · 5-lap test" with a
  success metric.
- Decoder changes: code-backed (decomp names the source) **and** validated (MoTeC |r| ≥ 0.98 aligned, or an
  independent physical check). Serialize Ghidra jobs.

---

## Phase 0 — One decoder, green tests

- [x] Fix test collection imports and stale GO assertions (this repo) — 211 passed.
- [x] Align coach/RE skills + playbook with verified lane status.
- [x] `pip install -e ~/github/vre-rpy-cli`; replace `external/query_tools/acc_rpy/*` duplicates with thin re-exports
      of `vre_rpy` (keep module names so callers don't break). Private RE comments move to the playbook.
- [x] Add `vre-rpy-cli/tests/` (pytest). Fixtures via env `VRE_RPY_FIXTURES` (gitignored, never committed); tests skip
      when absent. CI-safe synthetic tests for pure functions.
- [x] Sync `~/.agents/skills/{acc-rpy-re,decomp-first-stream-re,ghidra-ida-re}` with the repo copies.

## Phase 1 — Decoder completeness (in `vre-rpy-cli`)

- [x] `arr30_decode`: add `vel_xyz_ms` (+16/+18/+20), `g_vert` (+26), `drivetrain_speed` (+22, hypothesis-named),
      `flags` (+32 bit0, bits1–4) with catalog status.
- [x] `pose_track`: wheels[4], `yaw_deg` from wheel axis, `slip_deg` = yaw − velocity heading (velocity from arr_30, not
      pose deltas), elevation `y`; tyre radii from hdr16 (wheel speed uses them, fall back to fit).
- [x] `frame_clock`: pose clock from wrap↔S/F anchors; input offset fitted per file; gate + report. (Final: lap-duration matching + coarse/fine speed lag field; per-lap gate.)
- [x] Lap matcher by session time (fixes off-by-one); line export uses best valid lap; no 8000-point thinning on the
      frames path.
- [x] `replay_frames`: full-rate per-lap columnar frames (distance along AI line, unwrapped), lazy-loadable.
- [x] Tests with golden values: Erik 135425 → 100% brake 242.5 m ± 3, minV 63.3 @ 356.5 ± 3; You 138525 → 273 m,
      58.0 @ 364.5; Erik segment↔lap mapping 136985/136990/135425; |v| vs speed r ≥ 0.9999.
- [x] Decode arr_24 predicted lap (`ref_ms`) and arr_10 counters (as `UNVERIFIED_*`); [ ] verification step for arr_10:
      record a replay with `acc_ingest.shm_logger` running and compare against SHM `carDamage[5]` / pad and disc life.
- [x] **1b:** MP leaderboard parse — fixed without Ghidra (missing blob + 0x7B length ambiguity); race replays expose every car (`--car-index`). [ ] Remaining: 2 replays with unparsed car records; race-lap sync 71–75 %. Decomp-first: re-read `FUN_140fda560`/leaderboard reader in existing
      outputs; only then a targeted export. Success = every car's rec_68/arr_30 extracted from a `*_mp.rpy`.

## Phase 1d — Track limits and lap validity (generic, learned per track)

Findings and numbers: playbook "Track limits (2026-11-21)". The game's verdict is in the file; *where* each cut
happened is learnable; *why* long-lag zones judge some passes and forgive others is not recoverable from position.

- [ ] `track_limits.py` (CLI): per frame, per side, how far the innermost wheel is beyond the fastlane edge;
      excursion events (start/end, peak margin, side, wheels over).
- [ ] Verdict attribution: for each invalidated lap, link the flag drop to its excursion with a per-track
      **zone model** (drop zone → excursion zone, lag) learned by voting over every replay of that track the user has
      (own + reference replays). Starts empty (fall back to "nearest excursion within 15 s") and improves with data.
      Output per lap: `valid`, `cut_at_m`, `cut_side`, `judged_after_s`, `zone_id`, `confidence`.
- [ ] Excursions that the flag can't show (after the first cut, or forgiven) are labelled "over the line — not judged"
      with margin; never "illegal".
- [ ] Legal track-use envelope per station: the widest all-4 position seen on **valid** laps (across all drivers)
      → coaching can say "the reference uses 0.6 m more exit kerb here, and valid laps prove it's allowed".
- [ ] Contact events from the tail blob as `UNVERIFIED_CONTACT` until checked against a replay with a known hit.
- [ ] Tests: Spa/Imola fixtures — attributed excursion within ±15 m of the cluster centre for ≥ 90 % of verdicts in
      known zones; short-lag zone geometry recall ≥ 0.85 at ≤ 10 % false alarms; works on a track with zero history.
- [ ] **Ghidra (decomp-first, gated):** writer of the arr_24 valid byte → cut-detection routine; success = predicting
      held-out invalidations at ≥ 90 % lap accuracy from frames alone. Until then, verdicts come only from the flag.
- [ ] Outputs: MoTeC `VRE_VALID`, `VRE_EDGE_MARGIN_L/R_M`, `VRE_CUT_EXCURSION` (flag), `VRE_CUT_JUDGED` (flag at the
      attributed excursion); viewer: wheels-over-line highlights on the map, per-lap cut cause, track-use envelope.

## Phase 1c — MoTeC export v2 (in `vre-rpy-cli`)

Fixes:
- [ ] `VRE_YAW_DEG` → real yaw rate from wheel-point heading (pose clock → input clock, fitted offset).
- [ ] Replace `VRE_TC_ACT` / `VRE_ABS_ACT` with `VRE_TC_EST` / `VRE_ABS_EST` (slip-ratio based, labelled estimates);
      write measured precision/recall per gold file into `drivers.json` and the channel comment; never call them state.
- [ ] Wheel speed from hdr16 radii; `VRE_US_OS` from yaw rate vs bicycle-model expected yaw (wheelbase from the wheel
      points, steering ratio from car config with a documented default) instead of a fixed 400° lock.
- [ ] `LAP_DIST` from pose (along AI line, resets at S/F) replaces the drifting `VRE_DIST_M` for lap overlays; keep
      Motec Corr Dist working (SPEED stays first in Internal Maths).

New channels (pose resampled onto the export grid; native rates recorded in channel comments):
- [ ] `GPS_LATITUDE` / `GPS_LONGITUDE` / `GPS_ALTITUDE` from pose XYZ (local tangent-plane projection) so Motec's Track
      Map draws the **driven line** for Main and Ref, not a speed/G reconstruction.
- [ ] `VRE_ELEV_M`, `VRE_GRADE_PCT`, `VRE_VERT_CURV` (κᵥ), `G_VERT`, `VRE_LOAD_TOTAL` (Σ tyre load) — terrain lane.
- [ ] `VRE_VEL_X/Y/Z`, `VRE_BETA_DEG` (body slip = yaw − course), `VRE_YAW_RATE`.
- [ ] `VRE_LAT_OFFSET_M` (from AI line), `VRE_EDGE_MARGIN_L/R_M` (closest wheel to each edge, negative = beyond the line).
- [ ] `VRE_VALID` (per-sample validity flag), `VRE_PRED_LAP_S` and `VRE_PRED_DELTA_S` (ACC predicted lap vs best),
      `VRE_CORNER_ID`, `VRE_PHASE` (brake/turn/apex/exit from Phase 3 events), `VRE_DT_REF` (Δt to Ref on distance).
- [ ] Event flags for the habits in Phase 4 (`VRE_EV_BRAKE_ON`, `VRE_EV_REBRAKE`, `VRE_EV_FT`, …) so a Motec user
      can jump to the same moments the viewer shows.
- [ ] Workbook: add a "VRE Corner" worksheet (distance axis: speed, brake, throttle, steer, Δt, elevation/κᵥ/G_VERT,
      edge margin) and a "VRE Terrain" worksheet; keep existing worksheets.
- [ ] `verify` gains checks: no all-zero VRE channel, proxy P/R recorded, GPS line within 2 m of the AI line on
      average, LAP_DIST resets at every BCN.

## Phase 2 — Track packs for every ACC track (generated, not hand-drawn)

- [ ] `vre-rpy track-pack <track>`: from `AC2/Content/Cache/<track>/fastlane.ai` build centreline, official edges,
      elevation, **corners** (AI-speed minima + curvature runs, merged into complexes), **direction** from curvature
      sign, braking zones, and **terrain features**: crests / dips / compressions from vertical curvature κᵥ with
      expected load change ≈ v²κᵥ/g at AI speed. Names from the curated list where one exists (20 packs), else "T<n>".
- [ ] Generate for all 27 installed tracks; validate directions against steering on any available replay.
- [ ] Remove hard-coded Spa/Monza lookups/lengths; steering lock from per-car config with documented default.
- [ ] **Optional track-knowledge layer** (`track_pack/<track>_notes.json`, researched per ACC track online): curated
      corner names, complexes, known track-limit hotspots, notable kerbs/dips/crests, landmark cues (boards, bridges).
      Rules: the generated pack is always the base; notes only **add labels and cues** and never change detection
      thresholds or maths; every note carries a source; the pipeline gives identical metrics with the notes removed.
      Test: run the full pipeline on a track with no notes file and on one with notes → same events and numbers.

## Phase 3 — Analysis core (generic, sanity-gated)

- [ ] Distance-aligned laps on fixed stations (every 2 m) → cumulative time; Δt vs reference; variance cliffs.
- [ ] **Replace bucket stitching** (A1): theoretical best = sum of best per-segment times from interpolated cumulative
      time; only completed, valid, flying laps; gates: `theoretical ≤ best`, lap within 0.9–1.3× median, else drop and
      say why. Same fix for the AC path (`LapTimeAnalyzer`) behind a test.
- [ ] Corner segmentation brake-to-brake (previous exit → next brake) per pack.
- [ ] Per-corner, per-lap **events**: brake onset, time/distance to peak (initial bite), peak decel (g from speed and
      g_lon), release shape (linear / stepped / double-hump), re-brake, trail depth at turn-in, entry speed, minV and its
      location vs apex, rotation (peak slip, yaw rate), throttle pickup, full-throttle-and-stay, sawtooth, coast gap,
      apex / exit edge margin (wheels), wheelspin (slip ratio rear), lock (slip ratio front), and **terrain context**
      (what the car was doing on each crest/dip: braking on a crest, throttle in a compression, measured load change
      from `tyre_load` sum and `g_vert`).
- [ ] Consistency per metric (median, IQR, n) and own-lap correlation with section time (|r| ≥ 0.4, n reported).

## Phase 4 — Habits, tendencies and the driver profile

**Taxonomy** (sources: HPAcademy brake-trace practice, Coach Dave brake-trace phases, Driver61/Autosport
over-slowing and "brake later" myth, repo playbook pattern library). Each habit has: detection rule on Phase 3 events,
corner classes it applies to, pace-impact measure, and a polarity (strength / weakness / neutral style).

| Group | Habits (examples) |
|-------|-------------------|
| Braking | late bite / slow ramp to peak; peak not at start; double-hump (release + reapply); square block (no trail); over-trail into lock; braking on crests |
| Entry | hero entry (high entry speed → re-brake → low minV); early turn-in; over-slowing (minV early, long plateau) |
| Rotation | waits for straight wheel; rotates at slowest point (V); throttle while still unwinding |
| Exit | late full throttle; sawtooth; lift after commit; wheelspin-limited vs not |
| Line / track use | apex margin, exit margin vs reference; uses / ignores kerbs and dips |
| Terrain | uses compressions for braking/traction; unloads car over crests |
| Consistency | high spread corners (where the gain usually is) |

- [ ] `habits.py`: per-corner instances → corner classes (slow/medium/fast × terrain) → a **habit** only when it repeats
      across ≥ 3 corners or ≥ 50 % of laps at one corner. Polarity from pace impact: Δt attributable vs reference
      **and** own-lap correlation; "style" (neither costs time) is recorded, not corrected.
- [ ] Reference profile built the same way from the reference replay (what the faster driver does differently).
- [ ] Driver profile v2 (`driver_profile.json`): ACC entries per car/track, cross-track constants (true habits), stated
      preferences (kept), trend vs previous sessions. Port `driver_lab style` metrics onto the generic events so AC and
      ACC share one profile schema; fix steer sign per source.

## Phase 5 — Coaching distiller (mental models, physics, one drill)

- [ ] Mental-model catalogue: each wrong model with its detection (from habits), the correct model, the physics
      reason, the drill, the success metric. Seed: "brake later = faster", "build brake pressure smoothly", "max speed at
      turn-in", "wait for a straight wheel before throttle", "brake through the crest", "the apex is where to slow".
- [ ] Ranker: pace impact × repeatability × fits-the-profile → top 1–2 for the session; others listed as "later".
- [ ] Physics explanations generated from measured terrain: e.g. braking zone uphill + compressing (grip available,
      gravity helps) → crest at turn-in (−0.10…−0.15 g vertical, lowest tyre load) → dip at apex (+30 % load) → use it
      for throttle/rotation. Numbers only from data; label "measured" vs "physics reasoning".
- [ ] Output `analysis/coaching.json` (habit ids, moment ids, citations) consumed by the coach agent and viewer.
- [ ] Skills: `vre-corner-coaching`, `vre-root-cause`, `vre-driver-profile`, `vre-teach-answer` read habits/profile;
      `coach_notes.py --at-m/--moment`.

## Phase 6 — Viewer

- [ ] Load rpy bundles (manifest/geometry/laps from frames; reference driver picker).
- [ ] **Corner Replay** (from prototype): map with 4-wheel footprints and pedal trails, two driver HUDs, Same place /
      Same moment, frame step, distance-aligned traces + **elevation / vertical-G / tyre-load lane** with crest/dip
      markers, moment cards.
- [ ] **Habits panel**: your strengths and weaknesses vs reference, per corner class, with "show me" links into Corner
      Replay; profile trend view.
- [ ] Session summary = the 1–2 distilled fixes, each linked to its moments.
- [ ] KPI sanity: hide/flag numbers that failed Phase 3 gates. Playhead/pins at the car's real position.

## Phase 6b — AI video review (the coach drives the replay)

Goal: the AI can work with the replay the way a coach uses video: pick moments from the whole-lap view, build corner
breakdowns, pause on frames, draw on the map and traces, and tie each point to the data.

- [ ] **Review document** `analysis/reviews/<id>.json` (schema in `types.ts` + JSON Schema): ordered *scenes*, each with
      `title`, `corner`, `s0/s1`, laps (yours / reference), alignment (same place / same moment), playback rate,
      `pauses[]` (metre → callout text), map view, highlighted trace lanes, overlays (pin, zone, arrow, line-on-map,
      text) at metres, WHAT/WHY/HOW narration, citations (event / habit / moment ids). Authored by AI or user;
      every number must resolve to a cited id (validated on save).
- [ ] **Review mode** in the viewer: plays a review like a coach session (auto-advance, pause at callouts, step,
      replay scene, next/previous), with the overlays drawn on Corner Replay.
- [ ] **Live control channel**: the launcher gains `/api/viewer` (server-sent events to the page + POST commands) and
      `/api/viewer/state` (playhead, lap, selection, current scene). Commands: `seek`, `play_range`, `set_mode`,
      `focus_corner`, `annotate`, `clear_annotations`, `open_review`, `add_scene`.
- [ ] **MCP server** (`external/query_tools/viewer_mcp`) exposing those as tools plus read tools
      (`get_state`, `get_frames(s0,s1,driver,lap)`, `get_events(corner)`, `get_habits`), so a Claude session can
      "see" what you're looking at and drive the replay while you watch. Coach panel chat answers with scenes, not only
      text.
- [ ] **Auto breakdown from the big view**: from the whole-lap Δt, take the top variance cliffs and generate one scene
      per cliff (Phase 3 events + Phase 5 coaching), ordered by time lost; user can reorder/delete.
- [ ] Annotations carry author (AI/user), lap, driver, metres, frame time; user can edit/delete; persist across
      re-exports (extends `coach_notes.json`).
- [ ] Skill `vre-video-review`: how to build a review (≤ 2 fixes, cite every number, show reference first then you,
      pause on the decisive frame, end with the drill + success metric). Pressure test: agent produces a valid review
      for a corner it hasn't seen.

## Phase S — Setup and vehicle dynamics (data + analysis + explanation, pace first)

Goal: know what the car is doing (loads, balance, platform, aero, tyres) from the data, what each setup change would
do and why, and use that to separate technique errors from setup needs.

**S1 — Data**
- [ ] Setup ingestion for every ACC car (`Setups/<car>/<track>/*.json`); session ↔ setup link via `--setup` on the
      CLI, or nearest file saved before the session start (shown, user confirms). Diff two setups in physical terms.
- [ ] Per-car **index → physical unit** tables (pressure psi, wheel rate N/mm, ARB, bump stop rate/window, damper
      clicks, ride height mm, toe/camber °, wing, brake bias, diff preload), researched online per car with sources;
      cars without a table fall back to click-relative reasoning (direction of change still valid).
- [ ] **Ghidra (decomp-first):** (a) confirm SaveReplay never serializes the setup; (b) find setup index→value
      conversion code in the EXE (if conversions are code, not pak data, they give exact units for every car).
- [ ] Data tiers, stated in every answer: replay only (≈ 8–11 Hz inputs, normalized suspension proxy); + MoTeC `.ld`
      of your own laps (200 Hz SUS_TRAVEL, tyre P/T) → full damper histograms; + `acc_shm` capture (pitch, roll, ride
      height, wheel load, slip angles).

**S1b — `vre-rpy setup`: setup extractor (CLI command)**

The replay does not store the setup (settled: full-file parse, 134 replays; playbook "Session lap records + setup").
So the command reports exact values where they exist and **estimates** everything else, always labelled.

- [ ] Rename the misnamed "setup" block to `session_weather` and decode it (ambient, cloud, rain, evolution) — exact.
- [ ] Exact from the replay: car, track, session type, weather config, static mass (garage samples), gearing (rpm vs
      speed per gear), tyre radii, wheelbase/track widths.
- [ ] Estimated **setup fingerprint**, pooled per session with uncertainty: aero load coefficient and aero balance
      (load vs v² on straights, gradient/kerb-filtered), rake proxy vs speed, roll and pitch gradients (sus proxy per g),
      brake balance (front/rear slip and load during straight-line braking), diff signature (inside-rear spin on exit,
      entry yaw under coast), TC/ABS activity signatures, ride-height proxy at speed.
- [ ] **Compare mode**: you vs reference in plain terms ("reference: ~3 % more aero load on the front at speed → more
      front wing or less rake"; "~1.5 % more rear brake bias"), with confidence and "can't tell" where the signal is weak.
- [ ] **Library match**: for your own sessions, rank the setup files in `Setups/<car>/<track>/` by fingerprint + saved
      time, and write a filled ACC setup JSON only when it is an exact library match; otherwise write
      `estimated_setup.json` with ranges, never a fake loadable setup.
- [ ] Calibration: sessions where the setup is known (library match confirmed by you) teach per-car mappings
      fingerprint ↔ setup values (e.g. aero balance per rear-wing click); estimates for unknown cars stay relative.
- [ ] Validation gate before any estimate ships as GO: on ≥ 2 known setup changes per estimated item, the fingerprint
      moves in the right direction and separates the setups. Cross-session tyre-pressure test (different cold
      pressures) decides whether pressure can be estimated at all.

**S2 — State estimation from any replay (car-agnostic)**
- [ ] Car parameters from the data itself: mass and weight distribution from static tyre loads, wheelbase/track from
      wheel points, tyre radii from hdr16.
- [ ] Per corner phase: lateral/longitudinal load transfer (from tyre loads), front/rear axle slip angles (bicycle
      kinematics from yaw rate, body slip, steer), understeer gradient, roll and pitch proxies (sus proxy L/R, F/R),
      aero load and aero balance vs speed (Σ load − weight vs v²; F/R split), rake proxy vs speed, braking/traction
      utilisation vs load, slip ratios, bump-stop/bottoming events (g_vert spikes + sus proxy saturation), brake temps.

**S3 — Physics model (calibrated on your data)**
- [ ] Quasi-steady model: load transfer split by roll-stiffness distribution (springs + ARB via the unit tables),
      tyre load sensitivity, aero balance vs ride height/rake, brake bias vs front/rear lock, diff preload/locking on
      entry and exit yaw. Dampers and bump stops as transient terms (how fast load moves, when stops engage).
- [ ] Sensitivities per car/track, e.g. "+1 rear ARB click → front roll-stiffness share −x % → about y° more rotation
      at z g mid-corner", with the assumptions printed. Calibrate signs and magnitudes against your own sessions with
      different setups; mark uncalibrated sensitivities as theory.

**S4 — Diagnosis (technique vs setup, pace first)**
- [ ] Symptom → cause chain: repeats across corners with clean inputs → setup candidate; tied to an input (e.g.
      re-braking on a crest) → technique; tied to terrain (crest unloading, compression into bump stops) → setup or
      line. Rank by expected lap-time gain, never by "calmer".
- [ ] Recommend at most 1–2 setup changes per session with the A/B protocol (`vre-acc-setup`), predicted effect,
      and what in the data should change if the model is right; record outcomes as setup episodes.

**S5 — Explanations and outputs**
- [ ] Explanations combine inputs + track + setup: what the car did, why (physics), what changes it (technique or
      setup), expected effect on pace. They attach to review scenes (Phase 6b) and to MoTeC channels
      (`VRE_AXLE_SLIP_F/R`, `VRE_UG`, `VRE_AERO_LOAD`, `VRE_AERO_BAL`, `VRE_ROLL_PROXY`, `VRE_PITCH_PROXY`,
      `VRE_LOAD_TRANSFER_LAT/LON`) and a "VRE Setup" worksheet.
- [ ] Skills `vre-acc-setup`, `vre-dampers`, `vre-explain-dynamics` updated to use S2–S4 outputs and the unit tables.
- [ ] Validation: mass from loads within 5 % of the car's known mass; aero load ∝ v²; on two of your sessions with a
      known setup change, the measured balance shift has the model's sign.

## Phase 7 — Verification

- [ ] `pytest` both repos; `npm run build`.
- [ ] Spa (You vs Erik), Monza, Imola: export → habits → coaching → viewer screenshots; numbers match Phase 1 goldens.
- [ ] Pressure check: coach agent with updated skills cites habits/moments, refuses NO-GO lanes, gives ≤ 2 fixes.

---

## Order and checkpoints

**No overfitting:** thresholds and models are fitted or checked on ≥ 3 tracks and are expressed relative to the car
(e.g. slip ratios, % of the driver's own peak decel), never as Spa/296 constants; the La Source goldens are
regression checks only.

0 → 1 → 1c/1d → 2 → 3 are the data foundation (1c can ship as soon as 1 lands, so MoTeC users get the fixes first); stop and report if sync gates or track packs fail on any of the 3 tracks.
4–5 (habits + distiller) next; 6 (viewer) can start in parallel once Phase 1 frames and Phase 3 events have schemas.
S1–S2 can run alongside 3–4 (same events and frames); S3–S5 after Phase 5. 6b after 6 (needs Corner Replay).

**Ghidra policy:** when the data can't answer a question (cut rule, setup units, unknown lanes), go decomp-first with
`decomp-first-stream-re` / `ghidra-ida-re` and the playbook before more correlation work. Serialize headless runs.

## Out of scope

3D/cockpit view (track assets unreadable; 2.5D elevation ribbon possible later); trackside landmark detection (boards,
kerb starts not in data — cues stay "unverified"); AC (non-ACC) sessions in Corner Replay beyond sharing the profile
schema.
