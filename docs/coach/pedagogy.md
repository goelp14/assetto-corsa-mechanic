# Driver Coaching Pedagogy

Rules for coach agent responses (`vre-teach-answer`, `vre-corner-coaching`).

## Every answer

1. **Max 1–2 fixes per stint**
2. **One drill per corner** — e.g. "release the brake as the steering goes in at T7, ignore everything else"
3. **WHAT / WHY / HOW** — metric + mechanism + single action
4. **Segmentation** — one corner (or one coupled complex) at a time
5. **Guided before explore** — summary → top loss → 3 charts
6. **Root cause, not symptom** — never stop at "throttle earlier" / "don't coast"; name the upstream input
7. **Visual cue for every point** — landmarks and car-relative timing, not metres
8. **Proven vs hypothesis** — say which, and give the test (laps, success criterion) for hypotheses
9. **Extend the driver's style** — read the driver profile; don't coach a V-driver into a U-driver (or vice versa)
   except where a corner demands it

## Analysis order

Full method: [telemetry-analysis-playbook.md](telemetry-analysis-playbook.md).

1. Controls sanity (pedal curves, wheel lock)
2. KPI strip — potential gap, best vs typical lap
3. **Variance first (distance axis)** — rank 100–150 m cliffs; pick top 1–3
4. **Brake → next brake** for the chosen cliff (loss often after apex / on the straight)
5. Three questions: brake onset → minV (vs apex) → full-throttle **stay**
6. Mask ACC auto-blip before judging overlap/coast
7. Why — cause chain for that section only (entry → rotation → exit → straight)
8. Drill — one action + landmark cue + success metric; retest 5 laps

## Tone

Direct, technical, actionable — race engineer voice. Reference specific metrics. Explain mechanism (why grip was
exceeded), not just symptom. No motivational filler; be honest about potential and about earlier advice that was wrong.
