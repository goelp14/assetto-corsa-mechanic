---
name: vre-teach-answer
description: Use when formatting the final driver-facing coaching response from collected evidence.
---

# VRE Teach Answer

Format evidence into actionable coaching copy.

## Conversation answers (chat / live coaching)

1. **Lead with the answer** in the first sentence ("Your Carousel time is lost on exit, and it comes from the entry").
2. **Chain, not symptom:** what the driver does → what the car does → what it costs → the one change.
3. **Numbers from the data only**, with comparison: fast passes vs slow passes, best vs typical.
4. **One or two fixes.** Each fix = action + visual cue + what it should feel like.
5. **Confidence:** say when a claim is proven on their laps vs a hypothesis to test, and what test would settle it
   (e.g. "5 laps entering a car width wider; success = no lift on exit").
6. **Corrections:** if an earlier cue was wrong (e.g. tyre stacks are the rotation point, not the apex), say it plainly once.
7. Plain words over jargon (beta → rear slide, delta_us → understeer angle, spline → track position/metres).
8. Tables only for short comparisons; the explanation goes in prose.

## App/CLI output template

```
**Summary** — 1–2 sentences

**What happened** — metric + citation [evidence_id]

**Why it matters** — mechanism (tyre load, grip envelope)

**What to do** — one drill for next session

**Drill:** <single actionable sentence>

Confidence: 0.xx | Citations: incident_0, corner_2
```

## Pedagogy constraints

Read [pedagogy.md](../../docs/coach/pedagogy.md):

- Max 1–2 fixes total
- One drill per corner
- Pair WHAT (awareness) + HOW (mental image / visual cue)
- No motivational filler; honest about potential and gaps

## Validation

Before sending:

1. Every number appears in the evidence pack or a `driver_lab.py` output you ran
2. Every citation_id exists in pack (bundle mode)
3. If confidence < 0.6, say "insufficient evidence" and name the missing channel or the test that would decide it

**REQUIRED SUB-SKILL:** Use `verification-before-completion`

## Deterministic fallback

If no LLM key: use `python -m external.query_tools.coach ask` — returns rule-based response from incidents/corner_reports.
