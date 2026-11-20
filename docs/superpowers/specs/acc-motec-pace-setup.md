# ACC MoTeC + GT3 pace setup — doctrine for VRE

**Goal:** unlock **repeatable lap time**, not a calmer car. Stability is a
constraint (finish the lap) only when it **helps pace** or **does not cost
pace** but raises consistency. "More stable but slower" ⇒ reject.

Sources blended here: Kunos `base_ACC` Motec worksheets, public ACC Motec
guides (SOLOX / Coach Dave / Trinacria), `gt3_physics_kb.json`, and **Sonoma
AC (312/67) lessons** that transfer to ACC GT3 coaching.

Last updated: 2026-11-19.

---

## Sonoma transfer (do not forget)

Validated on Ferrari 312/67 @ Sonoma Long (`vre-setup-and-controls`,
`vre-root-cause`, `docs/coach/dynamics-glossary.md`):

1. **Controls before setup.** Brake gamma 2.4 hid trail braking; calming the
   car (forward bias, soft bars, more coast lock) made it **stable and slower**.
   Fastest block was stock + a **gearing** (pace) change, not stability levers.
2. **Coast buckets:** A (rear step) was the *smallest* time loss. B (front not
   turning) + C (pedal gap) dominated. Do **not** assume "saving the car" →
   soft rear / more TC.
3. **Fastest passes can include rear slide** (~15° on hairpin). Rotation that
   points the car is pace; killing it for calmness is not.
4. **One lever + A-B-A.** Judge median flying laps; equal pace + better fit OK;
   calmer-but-slower reject.
5. **ACC has no gamma.ini**, but pedal habit / gaps still mask setup — fix
   technique windows before stacking TC/ABS or soft ARB.

---

## Motec worksheet → VRE channel → lever (pace-first)

Use Kunos workspace worksheets. Overlay a reference lap (Erik / personal best).
Only treat multi-corner patterns as setup; one-corner = driving.

| Worksheet | Read | VRE / GO channels | Lever class (try order) |
|-----------|------|-------------------|-------------------------|
| **Compare** | Where time is lost vs ref | SPEED, TIME, LAP_DIST | Driving first |
| **Driver** | Brake/throttle/steer shape, G | THROTTLE, BRAKE, STEER, G_*, `VRE_COAST`, `VRE_PEDAL_GAP`, `VRE_STEER_RATE` | Technique; only then setup |
| **Wheelspeed** | Spin / lock which corner | WHEEL_SPEED_*, SPEED, Motec TC/ABS **state**, `VRE_SPIN`, `VRE_LOCK`, `VRE_TC_ACT`, `VRE_ABS_ACT` | Diff exit, bias, TC/ABS **maps** only if intervention **costs lap time** |
| **Understeer / Oversteer** | Balance math (neg≈US, pos≈OS) | `VRE_US_OS`, steer, G_LAT, SPEED | Springs/ARB → aero (rake/wing) → diff; not dampers first |
| **Suspension Travel** | F vs R travel / pitch under brake & power | SUS_TRAVEL_* (Motec) or `VRE_RAKE_LOAD` / tyre_load proxy from rpy | Ride height / bumpstop / springs (aero platform) |
| **Suspension Histogram** | Damper velocity bell (slow/fast bump/rebound) | `VRE_DV_*` when SUS GO; else defer | Dampers **last** (1.10+), after springs/ARB sane |
| **Engine Revs** | Limiter / shift points | RPMS, GEAR | Gearing / shift — **pace lever** (Sonoma lesson) |
| **Tyres** (Channel report) | Hot psi / core | TYRE_PRESS_*, TYRE_TAIR_* | Pressures into **26–27 psi** dry hot; ducts/camber for 70–100 °C |
| **Section / Track report** | Rank corners by time loss | corner table / delta-to-ref | Focus A/B on top time-loss corners |

### Electronics (settings ≠ state)

| Dimension | Motec / HUD | VRE | Rule |
|-----------|-------------|-----|------|
| **Setting** | garage TC1/TC2/ABS/ECU; HUD Level | `VRE_TC_LEVEL`, `VRE_TCCUT`, `VRE_ABS_LEVEL`, `VRE_ENG_MAP` | Minimum maps that still allow exit/entry **pace** |
| **State** | Motec TC/ABS 0–1; HUD InAction | `VRE_TC_ACT`, `VRE_ABS_ACT` | Only raise maps if intervention **loses** time vs spin/lock cost |

Never bump TC/ABS for calm alone (`setup_hints` rejects `calm_only_tc`).

### Grip / environment

| Signal | Channel | Use |
|--------|---------|-----|
| Track grip | `VRE_TRACK_GRIP` ← weatherData[6] raw (name hyp) | Scale expectations; wet vs dry lever set |
| Lat demand | `VRE_LAT_UTIL`, G_LAT | Corner ranking for grip limit vs driver leave |

---

## ACC GT3 lever order (pace)

1. Tyres in window (pressure + temp)
2. Mechanical balance (springs/ARB) for multi-corner US/OS
3. Aero platform (ride height / rake / wing) — slow vs fast US/OS split
4. Diff entry/mid/exit for rotation vs exit traction
5. Brake bias / migration with ABS **state** evidence
6. Dampers (histogram) for kerbs/transitions
7. Electronics maps — last amplifier

Reject pre-1.9 pressure dogma (~27.5–29 hot). KB verified **1.10.3**.

---

## Export wiring

`export_rpy_analysis` writes Motec `.ld` + `setup_calcs/*.json` with the VRE_*
set above. Agents must cite worksheet + channel when recommending a lever.
File NO-GO (tyre_press/tair/sus_mm/TC·ABS packer) ⇒ say so; use Motec gold or
`--electronics` for levels; do not invent.

Companion module: `external/query_tools/acc_rpy/motec_worksheets.py`
(`worksheet_map()` for agent packs).
