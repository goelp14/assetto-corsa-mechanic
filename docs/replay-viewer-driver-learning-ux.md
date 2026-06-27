# VRE Replay Viewer: Driver Learning UX & Telemetry Display Research

**Date:** 2025-06-23  
**Scope:** How to teach drivers effectively from stint telemetry on the web — pedagogy, industry conventions, cognitive science, and performance engineering.

This document synthesizes freely available coaching material (Ross Bentley / Speed Secrets, Virtual Racing School, sim-racing telemetry tools), sports-learning research (cognitive load theory, video-based motor learning), dashboard design literature, and web telemetry performance practice. It maps findings to the current `replay-viewer/` architecture and proposes a prioritized product direction.

---

## 1. What drivers actually need to learn

### 1.1 Deliberate practice, not “faster laps”

Ross Bentley’s coaching framework (deliberate practice, Ericsson) is explicit: **break driving into discrete skills and practice one at a time**. Turning laps hoping for a faster time is inefficient. Sessions should target specific techniques — brake release shape, throttle re-application point, minimum speed at apex — not whole-lap heroics.

**Implication for VRE:** The viewer is not a data dump. It is a **practice planner**. Every screen should answer: *“What is the one thing I change next session?”*

### 1.2 Mental image + awareness = growth (MI + A = G)

Bentley’s learning formula: a vivid **mental image** of the target behavior plus honest **awareness** of current behavior lets the brain close the gap. Telemetry supplies awareness; coaching copy supplies the mental image.

**Implication:** WHAT/WHY/HOW + evidence must stay paired. Raw traces without a single actionable sentence fail the formula.

### 1.3 Coaching with data: limit focus to ~2 changes

In Bentley’s Watkins Glen example, two data-backed instructions were enough for a session:

1. Spend ~3% more of the lap at full throttle.  
2. Experiment with brake release timing in turns 6–9.

He explicitly notes he would have split these across two sessions if time allowed.

**Implication:** After stint analysis, surface **at most 1–2 prioritized fixes** with corner scope — not twelve annotation chips.

### 1.4 The standard telemetry reading pass (F1 / sim racing)

Industry-standard analysis order ([Podium Prophets](https://podiumprophets.com/blog/reading-f1-telemetry-beginners-guide), VRS, Apex):

| Step | Question | Primary view |
|------|----------|--------------|
| 1 | Where was the lap won/lost? | Sector or corner Δt |
| 2 | Straight, brake, mid-corner, or exit? | Speed trace for that segment |
| 3 | Who got to power first? | Throttle trace |
| 4 | Who braked later / trailed better? | Brake trace |
| 5 | Is it one-lap or stint pattern? | Stint pace / consistency |

**Implication:** Default layout should follow this **workflow order**, not channel catalog order.

### 1.5 One fix per corner, then drill

Sarah Moore Racing and VRS emphasize: identify the **largest single loss**, design a **drill** (e.g. “brake 3 m later at T3, ignore everything else”), verify on the next outing.

**Implication:** Time-loss panel + corner zoom + filtered debrief is the right spine. Missing piece: explicit **“Your drill for next session”** card per corner.

---

## 2. Cognitive science constraints

### 2.1 Cognitive Load Theory (CLT)

Working memory is small. Load splits into:

- **Intrinsic** — task difficulty (reading 12 charts at once).  
- **Extraneous** — bad UI (split attention, clutter, unexplained colors).  
- **Germane** — productive schema building (comparing *your* brake release to *reference* at one corner).

Research on dynamic visualizations ([PMC systematic review, 2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC7794790/)) finds effective designs use:

| Technique | Effect |
|-----------|--------|
| **Segmentation** | 10–20 s clips / one corner at a time |
| **Sequencing** | Show channels serially, not all at once |
| **Learner control** | Pause, replay, zoom, change speed |
| **Cueing** | Highlights + labels directing attention |
| **Worked examples** | Reference lap overlay before free exploration |

Novices need structure; experts tolerate concurrent views. VRE users span both — **progressive disclosure** is mandatory.

### 2.2 Video / self-review in sport

Recent sport-science opinion ([PMC, 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12979457/)): unstructured full-session video **increases extraneous load**. Segmented clips + guided reflection improve decision accuracy (~15% in cited youth-sport work).

**Implication:** Post-stint review should open on **summary → top loss corner → 3 charts**, not full channel list.

### 2.3 Motor learning stages

Cognitive → associative → autonomous ([sports injury / performance literature](https://www.sportsinjurybulletin.com/improve/state-of-mind-understanding-cognitive-load-in-performance-and-injury-rehabilitation)): new skills demand working memory; autonomous skills free attention for traffic, weather, etc.

**Implication:** Offer a **“guided” mode** (worked example + 2 tasks) and **“explore” mode** (all layers). Default guided.

---

## 3. Industry UI conventions (what works in the wild)

### 3.1 Distance on X-axis, synchronized crosshair

Universal across TRACE.IT, Rapid Telemetry, MoTeC-style tools, Braking Lab, iRacing overlays:

- **X = lap distance** (or spline 0–1), not time — enables head-to-head comparison when lap times differ.  
- **Linked cursor** across all distance charts + track map.  
- **Drag region** to zoom distance; double-click / reset to widen.  
- **Reference lap** as dashed overlay on same axes.

VRE already uses spline distance and uPlot sync — aligned with convention.

### 3.2 Inverted pyramid layout

Dashboard research (Carbon, Elastic, Few, Tableau eye-tracking):

1. **Top:** KPI strip — potential gap, best lap, theoretical best.  
2. **Middle:** *Where* — time-loss ranking + map.  
3. **Bottom:** *Why* — traces for selected corner only.  
4. **Side panel:** coaching narrative filtered to selection.

F-pattern: top-left gets first fixation. **Put “+0.43s at Turn 7” there**, not layer toggles.

### 3.3 Chart types per channel

| Channel | Convention | Avoid |
|---------|------------|-------|
| Speed | Line + optional ref overlay | Area fill that obscures delta |
| Brake / throttle | **Line traces** (%) | Pedal “strips” unless pro mode |
| Steering | Line or small area | Full-width heat strips |
| Δt | Line or diverging area | Unlabeled orange blobs |
| G-G | Scatter / friction circle | Same color as lap line |
| Grip % | Line with target band | No context band |

Pedal strips are useful in pro tools (MoTeC) but **novice sim coaches consistently start with three line traces**: speed, brake, throttle ([Apex Sim Racing](https://www.apexsimracing.com/blogs/sim-racing-blog/understanding-telemetry-iracing)).

### 3.4 Map semantics must be explicit

Users cannot infer orange vs green vs blue without a legend. TRACE.IT and Rapid Telemetry document: racing line, compare line, cursor, sector boundaries.

**Rule:** Every non-neutral color on the map needs a **text label in the UI**, not only hue.

### 3.5 Progressive disclosure for channels

Rapid Telemetry / TRACE.IT: core tabs first; suspension, damper, tire temp behind expansion.

VRE’s layer panel is correct structurally but should be **tiered**:

- **Session review (default):** speed, brake, throttle, Δt, map, debrief.  
- **Analysis:** time loss, G-G, grip, phase bands.  
- **Chassis:** wheel load, suspension, β, yaw.

---

## 4. Web performance for telemetry viewers

### 4.1 uPlot is the right baseline

[uPlot](https://github.com/leeoniya/uPlot) targets exactly this: canvas 2D, distance series, sync cursors, zoom — ~50 KB, handles 100k+ points with built-in decimation (LTTB-style path builder).

Author guidance:

- Throttle live updates to **~200 ms** (human reaction floor).  
- Avoid rebuilding charts when only cursor moves.  
- Decimate when points ≫ pixel width (uPlot does this automatically).  
- For millions of points × many series × 50 Hz streaming → WebGL (TimeChart, webgl-plot).

### 4.2 VRE-specific performance issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Lag on scrub | N charts × setCursor + React state per mousemove | Throttle playhead; decouple hover from React where possible |
| Lag on zoom | Each chart `destroy()` + `new uPlot()` on `viewRange` change | Single shared chart grid or update scales via `setScale` |
| Map jank | Reproject all overlays per frame | Screen-space overlay layer (done); spatial index for hit-test |
| Too many uPlot instances | 10+ modes × separate mount | Virtualize off-screen charts; **one “focus stack”** when zoomed |

### 4.3 MSc thesis: web telemetry dashboards

A motorsport telemetry MSc thesis ([D-NB, 2024](https://d-nb.info/1376366312/34)) evaluating web scrutineer dashboards concludes:

- Bundle context while preserving drill-down.  
- Manipulable interaction (zoom/pan/filter) over static dumps.  
- Simplicity (Tufte data-ink ratio) beats decorative gauges.  
- Canvas/WebGL beats SVG for large series; pre-process data server-side when possible.

VRE’s export pipeline (normalized samples, corner regions, time-loss JSON) is the right **server-side pre-process** — keep heavy analytics off the client.

---

## 5. Gap analysis: research vs current viewer

| Research principle | Current state | Gap |
|--------------------|---------------|-----|
| Inverted pyramid (loss first) | Time-loss panel exists but buried in scroll | Move to persistent top band |
| 5-step telemetry pass | Charts grouped by channel type | Add **“Analysis step”** wayfinding (1–5) |
| ≤2 fixes per session | Many annotation chips | **Session plan** card with top 2 |
| Segmentation / one corner | Corner select + zoom works | Add **corner-only default chart set** |
| Line traces for pedals | Fixed (PedalStrip removed) | ✓ |
| Map legend | Added | ✓ |
| Evidence as coaching facts | formatEvidence added | ✓ |
| Narrative filtered by corner | filterNarrative added | Improve matching (corner IDs in text) |
| Guided vs explore modes | Single layer panel | **Not implemented** |
| Drill statement per corner | primary_action in time_loss | Not surfaced as “next session drill” |
| Chart rebuild on zoom | Full uPlot recreate | Performance risk — **needs refactor** |
| Worked example overlay | Compare lap dashed line | Add **ghost lap** labeling + delta at cursor |
| Learner control (20 min blocks) | No session timer / break nudge | Optional coaching UX |
| Colorblind-safe | Red/green throttle/brake | Add pattern or labels in legend |

---

## 6. Recommended information architecture

### 6.1 Three modes

```
┌─────────────────────────────────────────────────────────────┐
│  KPI: 4.43s potential · Best 1:42.1 · Theoretical 1:41.7   │
├──────────────┬──────────────────────────────┬───────────────┤
│  Track map   │  GUIDED STRIP (max 2 items)  │  Debrief      │
│  + legend    │  "T7: +0.31s — trail brake"  │  (filtered)   │
│              ├──────────────────────────────┤               │
│  Corner list │  Step 2/5: Speed @ T7       │  Evidence     │
│              │  [speed][brake][throttle]    │  WHAT/WHY/HOW │
│              │  (only 3 charts when guided) │               │
└──────────────┴──────────────────────────────┴───────────────┘
```

**Explore mode** unlocks full layer panel + physics channels.

### 6.2 Corner focus contract

When corner C is selected:

1. Map zooms to C (with reset).  
2. Charts zoom to `[spline_start, spline_end]`.  
3. Debrief shows only sections mentioning C.  
4. Inspector shows top annotation + **drill line**.  
5. KPI shows **loss at C only**.

### 6.3 Sync contract (industry standard)

One `playheadSpline` state, throttled to 30–50 Hz:

- All distance charts (uPlot sync key).  
- Map playhead (screen-space).  
- Optional: numeric readout strip (speed, brake%, throttle% at cursor).

---

## 7. Prioritized implementation roadmap

### P0 — Learning outcomes (high impact, moderate effort)

1. **Session Plan card** — top 2 corners/fixes from `time_loss.json` + `primary_action`.  
2. **Guided layout** — default shows only speed/brake/throttle/Δt when a corner is selected; hide physics layers until toggled.  
3. **Analysis steps header** — “1 Where · 2 Speed · 3 Throttle · 4 Brake · 5 Verify” with active step highlight.  
4. **Drill line** in Inspector: “Next session: …” extracted from `fix_action` / `primary_action`.

### P1 — Performance (high impact, higher effort)

1. **Shared chart controller** — one uPlot instance per visible row; `setScale` on zoom instead of destroy/recreate.  
2. **Virtualize** chart list (render only visible + speed/brake/throttle when zoomed).  
3. **Playhead via ref** — avoid React re-render of full tree on scrub.

### P2 — Pedagogy polish

1. **Worked example mode** — toggle compare lap with delta callouts at cursor.  
2. **Segment replay** — 15 s “corner clip” mental rehearsal prompt post-review.  
3. **Expertise toggle** — “New to telemetry” hides G-G, grip, chassis by default.  
4. **Colorblind patterns** — dash/dot series differentiation beyond hue.

### P3 — Research validation

1. **Usability test** with 3 drivers: task = “find biggest loss and state one fix” — time-to-answer, errors.  
2. **A/B** guided vs explore layout on time-to-identify brake issue.

---

## 8. University & academic foundations (Stanford, MIT, CMU, UCSB)

This section extends the motorsport-specific research with **accredited university curricula and peer-reviewed work** on visualization, HCI, learning science, and motor skill — all directly transferable to VRE’s web replay viewer.

### 8.1 Information visualization & exploratory analysis

#### Shneiderman’s visual information-seeking mantra (taught at MIT & Stanford)

Ben Shneiderman’s *“The Eyes Have It”* (1996), assigned in [MIT 6.859 Interactive Data Visualization](https://vis.csail.mit.edu/classes/6.859/) and [Stanford CS448B](https://online.stanford.edu/courses/cs448b-data-visualization), defines the canonical exploration loop:

> **Overview → zoom & filter → details-on-demand**

Seven tasks: overview, zoom, filter, details-on-demand, relate, history, extract.

**VRE mapping:**

| Mantra step | VRE implementation | Gap |
|-------------|-------------------|-----|
| Overview | Stint KPI + full lap map + time-loss rank | KPI not sticky enough |
| Zoom & filter | Corner select, drag-zoom on charts | ✓ (recent fixes) |
| Details-on-demand | Inspector WHAT/WHY/HOW + evidence | ✓ |
| Relate | Compare lap overlay + Δt | Partial — delta callouts weak |
| History | Zoom toolbar + reset | Partial — no undo stack |
| Extract | Export bundle | ✓ (backend) |

The viewer should **never** open in “details” mode (12 charts). It should open in **overview**, with zoom/filter as the primary path into detail — exactly as MIT visualization courses teach for EDA.

#### MIT InfoDesign (Ben Fry) — sensemaking over chart decoration

[MIT InfoDesign](https://infodesign.mit.edu/syllabus/spring26) (Ben Fry) explicitly rejects “how to recreate popular charts online” in favor of **making sense of data and helping others do the same**. Course flow: storytelling → perception & representation → discovery & analysis.

**VRE mapping:** The debrief narrative is the “story.” Charts are evidence for the story, not the product. Fry’s framing supports putting **Session Plan + corner narrative above the chart stack**, with charts as supporting exhibits.

#### Stanford CS448B / MATSCI122 — perception + cognitive science in viz design

[Stanford CS448B](https://online.stanford.edu/courses/cs448b-data-visualization) grounds visualization in **graphic design, perceptual psychology, and cognitive science**. [MATSCI122 Visual Communication](https://bulletin.stanford.edu/courses/2263051) applies the same stack to technical teaching.

[Stanford EDUC 299x: Visualizations in Learning](https://web.stanford.edu/class/educ299x/index.html) defines visualization as *“computer-supported, interactive, visual representations of data to **amplify cognition**.”*

**VRE mapping:** Every chart must answer a cognitive task (“where did speed diverge?”), not display a channel because it exists in the log file.

---

### 8.2 HCI & conceptual models (Stanford CS147, Norman)

[Stanford CS147](https://hci.stanford.edu/courses/cs147/) (Landay / dt+UX) teaches Don Norman’s interaction principles from *The Design of Everyday Things*:

- **Conceptual model** — user’s mental picture of how the system works  
- **Discoverability** — affordances, signifiers, constraints, mappings, feedback  
- **System image** — what the UI actually communicates

Design guides ([CS147 lecture on conceptual models](https://hci.stanford.edu/courses/cs147/2024/au/lectures/10-conceptual-models.pdf)):

1. Provide a good conceptual model  
2. Make things visible  
3. Map controls to the user’s model  
4. Provide feedback  

**VRE mapping:**

| Norman principle | VRE application |
|------------------|-----------------|
| Conceptual model | User thinks: “I pick a corner → I see why I lost time → I get a drill.” Not: “I toggle layers.” |
| Signifiers | Legend on map, labeled zoom window, step numbers in analysis |
| Mapping | Drag on chart = zoom **that segment**; corner click = filter **that coaching** |
| Feedback | Playhead sync, zoom toolbar state, selected corner highlight |

Mismatch example: unexplained map colors violated the system image — fixed with legend, but **guided mode** is still needed so the default model is “coaching” not “data explorer.”

---

### 8.3 Perception for design (Colin Ware — standard viz curriculum)

Colin Ware’s *Information Visualization: Perception for Design* (cited in university viz courses worldwide) distinguishes:

- **Pre-attentive processing** (<250 ms): form, color, motion, spatial position — processed without focused attention  
- **Attentive processing**: serial, limited to ~3–4 objects between glances

**Encoding rules for dashboards (Ware / Few synthesis):**

- Use **position and length** for quantitative data (speed, Δt) — strongest channels  
- Limit **hue** to ≤5 distinct meanings; never rely on color alone (colorblindness ~10% male)  
- Reserve **saturation/motion** for alerts (time loss, corrections)  
- **Gestalt proximity** groups related charts (speed/brake/throttle together)

**VRE mapping:**

- Speed/brake/throttle as **lines** with position encoding on Y — correct  
- Time-loss regions as **subtle bands**, not thick competing colors — improve  
- Playhead as **fixed-pixel marker** (spatial position pre-attentive) — done on map  
- Add **pattern** (solid vs dashed) for compare lap — P2 colorblind fix

---

### 8.4 Multimedia learning (UCSB — Richard Mayer, 200+ experiments)

Richard Mayer (UC Santa Barbara) [*Multimedia Learning*](https://www.cambridge.org/us/universitypress/subjects/psychology/educational-psychology/multimedia-learning-3rd-edition) is the standard university text for learning from words + graphics. Meta-analyzed effect sizes ([Mayer 2017](https://onlinelibrary.wiley.com/doi/10.1111/jcal.12197)):

| Principle | Effect (d) | VRE application |
|-----------|------------|-----------------|
| Multimedia (words + graphics) | 1.67 | Map + traces + coaching text together |
| Coherence (remove extraneous) | 0.70 | Hide physics layers by default; no chartjunk |
| Signaling (highlight essentials) | 0.46 | Corner bands, time-loss rank, drill line |
| Spatial contiguity | 0.79 | Inspector adjacent to charts; map near traces |
| Temporal contiguity | 1.30 | Synced playhead across map + charts |
| Segmenting | 0.70 | Corner zoom = one segment at a time |
| Pre-training | 0.46 | “How to read telemetry” micro-guide for novices |
| Personalization | 0.79 | Conversational debrief tone (VRE narrative) |

**Critical VRE violations Mayer would flag:**

1. **Redundancy** — showing pedal strip + line chart for same channel  
2. **No segmenting** — full-lap 12-chart view on load  
3. **Split attention** — debrief not filtered when corner selected (partially fixed)

---

### 8.5 Intelligent tutoring & learning by doing (Carnegie Mellon LearnLab)

CMU **Cognitive Tutors** ([Anderson et al., 1995](http://act-r.psy.cmu.edu/papers/Lessons_Learned.html); [LearnLab wiki](https://learnlab.org/wiki/index.php?title=Cognitive_tutor)) embody ACT-R theory: **procedural skill is acquired by doing, not by being told.**

Eight tutoring principles (abridged for VRE):

| CMU principle | VRE translation |
|---------------|-----------------|
| Represent competence as steps | Corner phases: entry → apex → exit |
| Learning by doing | Viewer follows stint the user actually drove |
| Model tracing | Compare user trace to reference / stitched best |
| Immediate error feedback | Show Δt + evidence at the moment of loss |
| Minimize cognitive load | Guided mode, 2 fixes max |
| Problems at the edge of ability | Rank corners by loss; start with largest gap |
| Communicate goal structure | “Recover 0.31s at T7 by…” |
| Abstract understanding | WHY mechanism, not only WHAT |

Cognitive tutors present as **tools**, not human emulations — aligns with VRE as engineer/coach assistant, not fake persona.

**VRE mapping:** `time_loss.json` + annotations are already a **model**. The viewer should **trace** the driver through the model step-by-step (corner → evidence → drill), not dump the whole model at once.

---

### 8.6 Computational cognitive science (MIT 9.52 / 9.66)

MIT [Computational Cognitive Science](https://ocw.mit.edu/courses/9-66j-computational-cognitive-science-fall-2004/) (Tenenbaum) studies how people **induce structure from sparse data** — exactly what a driver does comparing two laps.

Key idea: humans learn faster when data is presented in **structured hypothesis spaces** (trees, sequences) with **worked examples**.

**VRE mapping:**

- Corner list = tree structure over the lap  
- Reference lap = worked example  
- Δt curve = hypothesis generator (“loss is here, not there”)

---

### 8.7 Motor learning & feedback timing (Stanford Shape Lab, visuo-motor research)

Stanford [Shape Lab](https://shape.stanford.edu/research/motorLearning/) studies **explicit error-based sensory feedback** for motor learning. Related findings:

- **Persistent visual feedback** (seeing your trace evolve against reference) improves accuracy more than non-persistent feedback ([PMC8405669](https://pmc.ncbi.nlm.nih.gov/articles/PMC8405669/))  
- **Real-time** error feedback targets implicit learning; **post-hoc** feedback targets explicit analysis ([surgical motor learning study, 2025](https://arxiv.org/html/2508.17830v1))  
- Stanford [AAALab](https://aaalab.stanford.edu/) — perceptual skills can be **recruited for learning structure** when instruction is designed around them (symmetry → integers study generalizes to “design around perceptual affordances”)

**VRE mapping:**

| Phase | Feedback type | UI |
|-------|---------------|-----|
| In car (live) | Real-time | AC app coaching — out of scope for replay viewer |
| Post-stint (replay) | Post-hoc explicit | Replay viewer — **must** support persistent compare trace + segment scrub |

The replay viewer is explicitly the **post-hoc explicit learning** tool. It should optimize for **persistent overlay** (your line vs reference on map and traces) and **segmented replay**, not try to simulate in-car real-time coaching.

---

### 8.8 Active learning & mastery (MIT TEAL / MITx)

MIT [TEAL](https://web.mit.edu/jbelcher/www/TEALref/TEALarticle.pdf) (Technology-Enabled Active Learning) for physics shows **~2× learning gains** vs lecture-only when students:

- Engage actively (not passive watching)  
- Get **immediate formative feedback**  
- Use **spaced modules** with increasing complexity  
- **Revise** until mastery (specification grading initiatives)

[MITx + TEAL](https://openlearning.mit.edu/mit-faculty/residential-digital-innovations/teal-mitx): 95% of students wanted continued use — **timely feedback** was the top cited benefit.

**VRE mapping:**

| TEAL element | VRE feature |
|--------------|-------------|
| Pre-class learning sequence | Optional “telemetry literacy” primer |
| In-class active problems | Corner drill selection |
| Immediate feedback | Δt + evidence at cursor |
| Spaced modules | Corner-by-corner review order |
| Mastery / resubmit | “Did next stint fix T7?” — future stint comparison |

---

### 8.9 Integrated framework: university research → VRE architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 1: Overview (Shneiderman)                                │
│  KPI + time-loss rank + map                                     │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 2: Segment (Mayer segmenting + CLT)                      │
│  One corner selected → zoom all views                           │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 3: Relate (Ware pre-attentive + Mayer spatial contiguity)│
│  Speed / brake / throttle + compare lap, synced playhead          │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 4: Tutor (CMU model tracing)                             │
│  Evidence → mechanism → drill (≤2 per session)                  │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 5: Explore (MIT EDA / Stanford CS448B)                   │
│  Optional physics channels, G-G, export                         │
└─────────────────────────────────────────────────────────────────┘
```

**Norman discoverability** wraps all layers: user always knows which layer they are in and what action is available next.

---

### 8.10 Additional P0 items from university research

Beyond motorsport P0 (Session Plan, guided layout):

1. **Mayer coherence audit** — remove any redundant encodings (same data in two chart types).  
2. **Shneiderman-compliant default** — load overview only; details on corner click.  
3. **CMU-style goal header** — “Today’s goal: fix exit throttle at T7 (+0.31s).”  
4. **Ware encoding audit** — position/length for quantities; hue only for categories.  
5. **TEAL-style formative check** — optional “Can you name the biggest loss corner?” before revealing answer.

---

## 9. Sources

### University courses & programs

- [Stanford CS448B — Data Visualization](https://online.stanford.edu/courses/cs448b-data-visualization)  
- [Stanford CS147 — HCI & Design Thinking](https://hci.stanford.edu/courses/cs147/)  
- [Stanford EDUC 299x — Visualizations in Learning](https://web.stanford.edu/class/educ299x/index.html)  
- [Stanford LSTD — Learning Sciences & Technology Design](https://ed.stanford.edu/academics/doctoral/LSTD)  
- [Stanford MATSCI122 — Visual Communication](https://bulletin.stanford.edu/courses/2263051)  
- [MIT 6.859 — Interactive Data Visualization](https://vis.csail.mit.edu/classes/6.859/)  
- [MIT InfoDesign — Working with Data](https://infodesign.mit.edu/syllabus/spring26)  
- [MIT 9.52/9.66 — Computational Cognitive Science (OCW)](https://ocw.mit.edu/courses/9-66j-computational-cognitive-science-fall-2004/)  
- [MIT 9.081 — Human Memory and Learning (OCW)](https://ocw.mit.edu/courses/9-081-human-memory-and-learning-fall-2002/)  
- [MIT TEAL — Active Learning in Physics](https://web.mit.edu/jbelcher/www/TEALref/TEALarticle.pdf)  
- [MIT Open Learning — TEAL + MITx](https://openlearning.mit.edu/mit-faculty/residential-digital-innovations/teal-mitx)  
- [CMU LearnLab — Cognitive Tutors](https://learnlab.org/wiki/index.php?title=Cognitive_tutor)  
- [CMU ACT-R — Cognitive Tutors: Lessons Learned](http://act-r.psy.cmu.edu/papers/Lessons_Learned.html)

### Academic books & papers

- Ben Shneiderman, [*The Eyes Have It* (1996)](https://hci.stanford.edu/courses/cs448b/papers/shneiderman96eyes.pdf)  
- Don Norman, *The Design of Everyday Things* (human-centered design)  
- Colin Ware, *Information Visualization: Perception for Design*  
- Richard Mayer, [*Multimedia Learning* (3rd ed., Cambridge)](https://www.cambridge.org/us/universitypress/subjects/psychology/educational-psychology/multimedia-learning-3rd-edition)  
- Mayer (2017), [Using multimedia for e-learning](https://onlinelibrary.wiley.com/doi/10.1111/jcal.12197)  
- Anderson et al. (1995), [Cognitive Tutors: Lessons Learned](http://act-r.psy.cmu.edu/papers/Lessons_Learned.html)  
- Stanford Shape Lab, [Motor learning & sensory feedback](https://shape.stanford.edu/research/motorLearning/)  
- [Persistent visual feedback & visuo-motor skill (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC8405669/)

### Driver coaching & telemetry practice

- Ross Bentley, [Speed Secrets: How to Practice](https://rossbentley.substack.com/p/speed-secrets-how-to-practice) — deliberate practice, 20-minute blocks.  
- Ross Bentley, [Speed Secrets: Coaching With Data](https://rossbentley.substack.com/p/speed-secrets-coaching-with-data) — two-fix rule, speed-trace-first.  
- [Virtual Racing School — Practising efficiently: Analysing](https://virtualracingschool.com/academy/iracing-career-guide/second-season/practising-efficiently-analysing/) — synced video + telemetry.  
- [Podium Prophets — Reading F1 Telemetry](https://podiumprophets.com/blog/reading-f1-telemetry-beginners-guide) — 5-step pass.  
- [Sarah Moore Racing — Telemetry for improvement](https://sarahmooreracing.com/how-drivers-can-use-telemetry-data-to-improve-racing-skills/) — one drill per issue.  
- [TRACE.IT](https://github.com/naizens/TRACE.IT) — distance-synced charts, map cursor.  
- [Rapid Telemetry](https://github.com/mhmatthew/rapidtelem) — browser-local IBT, synchronized zoom.  
- [Braking Lab — Lap Comparison](https://www.brakinglab.com/en/docs/telemetry/lap-comparison) — corner breakdown table.

### Learning science

- [PMC — Instructional design for dynamic visualizations (2021)](https://pmc.ncbi.nlm.nih.gov/articles/PMC7794790/) — segmentation, learner control, CLT.  
- [PMC — Self-video modeling in youth sport (2025)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12979457/) — extraneous load from unstructured video.  
- [InnerDrive — Coach’s guide to CLT](https://www.innerdrive.co.uk/blog/coach-guide-cognitive-load-theory/) — worked examples, redundancy effect.  
- [The Decision Lab — Cognitive Load Theory](https://thedecisionlab.com/reference-guide/psychology/cognitive-load-theory).

### Dashboard & visualization design

- Stephen Few — dashboard principles (context, measure, layout, color).  
- Edward Tufte — data-ink ratio.  
- [Carbon Design System — Dashboards](https://v10.carbondesignsystem.com/data-visualization/dashboards/) — hierarchy, progressive disclosure.  
- [Elastic UI — Dashboard good practices](https://eui.elastic.co/docs/dataviz/dashboard-good-practices/).

### Web performance

- [leeoniya/uPlot](https://github.com/leeoniya/uPlot) — performance characteristics, decimation, throttle guidance.  
- Web telemetry MSc thesis — [d-nb.info/1376366312/34](https://d-nb.info/1376366312/34).

---

## 10. Summary

The replay viewer should be judged as a **coaching instrument**, not a telemetry browser. Research across professional driver coaching, sim-racing tools, sports-learning science, **and university programs in visualization (Stanford/MIT), HCI (Norman/CS147), multimedia learning (Mayer/UCSB), intelligent tutoring (CMU), and motor feedback (Stanford)** converges on the same pattern:

1. **Rank where time was lost** (corner/sector Δt).  
2. **Zoom to one segment**.  
3. **Compare speed → throttle → brake** against a reference.  
4. **Assign one or two drills** for the next session.  
5. **Reduce cognitive load** via segmentation, legends, and progressive disclosure.

Recent UX fixes (map scroll isolation, line graphs, evidence formatting, corner-filtered debrief) address **extraneous load** and **industry conventions**. The largest remaining gaps are **pedagogical structure** (guided mode, session plan, analysis steps) and **performance architecture** (shared chart lifecycle, virtualization).

**Next step:** approve P0 items for implementation, or run a short usability test on the current viewer before building guided mode.
