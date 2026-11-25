# Telemetry analysis playbook (ACC / GT3)

How to turn Motec / pose overlays into **useful** coaching — not vibes, not pedal myths.
Synthesized from MoTeC i2 training, HPA driver-analysis process, Popometer (Nils), SOLOX/Lorandi ACC Motec guide, ACCReplay, GitGud GT3 technique, Coach Dave / Track Titan Spa+296 material, and AiM “what/where/why”.

**Read this before any ACC lap-compare coaching.** Pair with `pedagogy.md`, `vre-collect-evidence`, `vre-teach-answer`.

---

## 0. Non-negotiables

| Rule | Why |
|------|-----|
| **Distance axis, never time** | Time-align drifts as the slower lap falls behind; events no longer share track position (MoTeC i2 seminar). |
| **Variance / delta first** | Steepest slope = where to zoom. Do not start on dampers or “smoothness” (HPA, SOLOX Compare). |
| **Brake → next brake = one section** | Time loss often lands **after** the apex, on the following straight (Popometer). |
| **Driving before setup** | Setup only when own laps are consistent (~≤0.5 s scatter). Otherwise you are tuning noise (SOLOX). |
| **≤ 3 technique notes; prefer 1–2** | HPA max 3; our pedagogy max 1–2 with one drill. |
| **Mask ACC auto-blip** | Mid-brake THROTTLE spikes on downshift are ECU rev-match, not driver overlap (Popometer map yellow; community Motec). |
| **Reference quality** | Same car; prefer a lap ~0.3–1.0 s ahead for learning. A 3 s alien differs *everywhere* — still usable if you only attack the **top variance cliffs**, not every trace wiggle (SOLOX, ACCReplay). |
| **Match conditions** | Air/track temp, fuel, tyre age, patch. Gap ≠ pure skill (ACCReplay regulated boards). |

---

## 1. Engineer loop (every debrief)

```
Collect → Compare (distance) → Variance map → Top 1–3 cliffs
  → Full brake-to-brake section
  → Standard checks (when / how fast / how much / how long / sequence)
  → Map: position, apex, min-speed point, track use
  → Cause chain (entry → rotation → exit → straight)
  → One action + landmark cue + success metric
  → Retest 5 laps → re-read variance
```

### 1.1 Variance triage

1. Overlay main (driver) vs reference on **corrected / integrated distance**.
2. Plot cumulative time variance (Motec F3 / Δt from ∫(1/v) dd).
3. Rank **100–150 m** windows by Δvariance.
4. Keep the **top 3**. Note whether loss is entry, mid, exit, or **post-exit straight** (Popometer pattern: loss after apex where speed gap is large).
5. Also overlay driver-vs-self previous run if working a drill (HPA).

### 1.2 Three questions per corner (Compare worksheet)

Ask **in order** (SOLOX / race-engineer debrief):

1. **Where do I brake?** Onset distance + peak pressure shape (not “later” alone).
2. **What is minimum speed?** Where it occurs vs apex; duration spent *near* minV (overslow plateau).
3. **When am I at full throttle and stay there?** First thr≥95 that **holds** beats an early dab that lifts.

Only then: steering sawteeth, TC/ABS activity, line on map.

### 1.3 Standard checks (Popometer)

For each input (throttle, brake, steer), write five words:

- **When / where**
- **How quickly** (ramp)
- **How much** (peak)
- **How long**
- **Sequence / sync** (brake vs steer vs throttle)

Map checks:

- Car placement vs reference
- Apex (closest to inside) — early/late/double
- **Slowest point** vs apex (often *before* throttle; can extend under partial throttle)
- Track used (exit kerb, sausage, paint)

### 1.4 Pedal hygiene (ACC-specific)

| Trace feature | Meaning | Do **not** say |
|---------------|---------|----------------|
| Brief thr spike under high brake + gear−1 | Auto-blip | “You’re overlapping” / “heel-toe” |
| Single sample thr+brk at 8 Hz | Pedal swap / sample edge | “Hold throttle while braking” |
| Long thr=0 and brk=0 between | True coast gap | — |
| Thr up → down → up on exit | Not ready / correction | “Be smoother” without timing fix |
| Square brake block | No trail; front unloads at turn-in | Only “brake later” |

**Mask rule:** zero THROTTLE for analysis when `brk>30` and (recent downshift **or** isolated 1-sample spike). Score coast / overlap / pedal-gap on the masked series.

---

## 2. Pattern library (what the delta usually means)

From Popometer + GitGud GT3 + Blayze trail-brake data:

| Pattern | What you see | Useful advice |
|---------|--------------|---------------|
| **Exit / straight bleed** | Variance flat in corner, climbs on next straight; speed gap grows while both “full” | Fix **exit speed & FT stay** — not apex heroics. Long next straight → exit wins (Spa LS→Kemmel). |
| **Overslow** | MinV early, then long flat speed; hard brake + rising steer; partial thr cruising | **Brake less**, leave grip for steer. Brain says “too fast”; data says “too much brake”. |
| **Hero entry, dead exit** | Later/harder brake, lower mid, late FT; may even win to apex then lose after | Earlier patience on entry; prioritise rotation→FT. |
| **Throttle sawtooth** | 60→40→100 | Wait, then **one** committed application (binary-ish GT3). |
| **Trail too heavy** | ABS while steered; steering grows without LatG | Peak brake wheels straight; be light on trail before lock (GitGud ~light trail in slow GT3 — car-specific). |
| **High-downforce fear** | Fast corners: square brake, no trail, huge scrub | Learn pitch/balance; careful trail + smooth steer (Popometer Pouhon-type). |
| **Rotation snapped in ("1 → 3")** | Yaw rate jumps right after turn-in (high `rotation_jerk_dps2`), slide, correction, then understeer | Small first input; add lock only as the brake bleeds off; one continuous build to the MRP ([rotation doc](rotation-and-corner-structure.md)) |
| **Brake straight, then turn** | Speed already at its minimum by turn-in; ref still sheds speed while rotating (`kmh_lost_turn_in_to_mrp`) | Carry some brake past turn-in and release it *with* the steering (closing spiral) |
| **Grip gap** | Combined-g dip between braking and turning; own slower laps have the bigger dip | Turn a fraction before each step of brake release; release length ≈ steering build |
| **Turned in too early** | A "waiting" phase under the limit: neither strong brake nor rising steer, then a second steering build | Turn in later, then build one motion; check "could the car have taken more?" |
| **Slowest point after the apex** | minV after apex; long part-throttle that doesn't accelerate | Slowest point slightly before apex; accelerate through it with *enough* throttle to accelerate |
| **Late apex hairpin done right** | MinV near/after geometric apex; FT soon after car pointed | Spa La Source: exit ≫ entry (Coach Dave / Track Titan / P1). |

**La Source (Spa) research notes**

- Brake ~100–120 m board; late apex; use inside dip for rotation; 1st/2nd by car.
- Priority: car rotated and on power for Eau Rouge / Kemmel (~25 s flat).
- Track Titan: late brake → longer hard pedal → delayed turn-in → lower minV → loss even if exit looks “straighter”.
- HYMO-style ref: often **near full throttle at/just after apex** while slower laps are still scrubbing.

---

## 3. GT3 technique anchors (for cause chains)

GitGud / ACC GT3 consensus used in coaching language:

1. **Straight brake** — quick peak, wheel ~straight; brief ABS OK.
2. **Release + turn** — add steer as pressure falls; below ABS before big lock.
3. **Rotation** — light trail + downshifts; steer is last tool.
4. **Throttle** — one committed go from a reference point (~mid corner / slightly earlier when pointed).
5. **Exit** — short TC flash OK; sustained TC light = sitting on limit.

296-specific (Coach Dave + Nils + car profile):

- Mid-engine; fronts slow to temp; 26–27 psi hot; 70–100 °C.
- Steering lock **400°** post-1.9.3 (ignore older 800° guides).
- ECU maps = **linearity only**, not power.
- Dash TC3 dead; use TC1/TC2.
- Hairpins: little deep brake; progressive throttle after car settles (~0.5 s in slow corners per Nils); early power unloads front / works diff — but release if you need rotation.
- Brake mostly straight; aggressive trail can step the rear.

---

## 4. Motec / ACC tooling checklist

1. Telemetry Laps > 0 on **loaded** setup; leave session before grabbing files.
2. Keep `.ld` + `.ldx` together.
3. Workspace: after `export_rpy_analysis`, double-click `motec/Open_VRE.bat` (writes `Documents\MoTeC\i2\Workspaces\VRE_Export` with Workbook XRefs — empty XRefs = blank Layouts). Or Kunos `base_ACC`.
4. Worksheets: **Compare** (80% of pace) → Driver → Wheelspeed → US/OS → only then Suspension histogram.
5. Corrected distance / stretch-to-track-length when comparing sessions (i2 Tools).
6. Offset axis (`O`) if beacons/SF disagree — align on a shared event (LS minV, Bus Stop brake).
7. VRE: pose-spline sync when Motec-only distance wraps disagree; never invent pedals from NO-GO rpy.

---

## 5. Advice quality bar (pass/fail)

A coaching line **fails** if it:

- Comes from time-aligned overlays
- Treats auto-blip as driver throttle
- Says only “don’t coast” / “brake later” / “throttle earlier” with no upstream cause
- Changes setup before driver consistency
- Gives >2 fixes for one stint
- Lacks a landmark cue and a retest success metric
- Ignores the following straight after a hairpin

A coaching line **passes** if it:

- Names the variance cliff (metres + Δt)
- Shows the brake→brake section chain with numbers (onset V, minV, FT-stay distance)
- Gives **one** change + visual cue + “success = …”
- Separates proven (on these laps) vs hypothesis (5-lap test)

---

## 6. Sources (research log)

| Source | Takeaway used |
|--------|----------------|
| MoTeC i2 Training Seminar (2008) | Distance overlay; variance F3; corrected distance; offset axis |
| HPA Professional Motorsport Data Analysis — Analyse Driver | Variance → top 3; brake/steer/throttle/XY G; max 3 changes |
| Popometer guide (Nils) | Brake-to-brake; when/how/how much; minV vs apex; overslow; auto-blip yellow; exit/straight bias |
| SOLOX ACC Motec (Lorandi) | Compare 3 questions; driving first; don’t chase aliens only |
| ACCReplay lap comparison | One corner; later brake ≠ full explanation; cause ≠ delta alone |
| GitGud GT3 + telemetry guides | Brake phases; trail; binary throttle; ABS while steered |
| AC Telemetrick | Auto-blip spikes under brake = downshifts |
| Coach Dave 296 + Spa guides | 296 character; LS exit priority; ER commitment |
| Track Titan Spa analyses | LS late-brake failure chain; FT at apex vs scrubbing |
| AiM / ACI race-data explainers | What/where/why; delta → speed → pedals → one fix → validate |
| Blayze trail-brake data | Peak vs trail shape; exit > early throttle dab |
| Suellio Almeida coaching videos (2025–26) | Corner = brake/closing spiral/MRP/opening spiral; rotation ∝ falling speed; brake release unlocks rotation; engine braking = dynamic brake bias; grip gap; balance trace |
| Nils Naujoks (Popometer) coaching + "track marks" | 2–3 targets per corner (apex, slowest point, apex 2); over-/under-turning patterns; braking cascades; damper histogram |

Update this file when a new technique proves out on VRE sessions — do not rediscover Motec basics in chat.
