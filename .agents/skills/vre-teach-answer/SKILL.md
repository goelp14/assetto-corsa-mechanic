---
name: vre-teach-answer
description: Use when formatting the final driver-facing coaching response from collected evidence.
---

# VRE Teach Answer

**Scope: Cross-game.**

Format evidence into actionable coaching copy.

## Conversation answers (chat / live coaching)

1. **Lead with the answer** in the first sentence ("Your Carousel time is lost on exit, and it comes from the entry").
2. **Open with the variance cliff** when comparing laps (“+0.4 s from LS exit to Raidillon”) — not a generic tip.
3. **Chain, not symptom:** what the driver does → what the car does → what it costs → the one change.
4. **Numbers from the data only**, with comparison: onset V, minV vs apex, FT-stay metre, exit V at fixed offsets.
5. **One or two fixes.** Each fix = action + visual cue + what it should feel like + success metric.
6. **Never** coach mid-brake throttle spikes as overlap — ACC auto-blip (see playbook + 296 `telemetry_pitfalls`).
7. **Confidence:** proven on these laps vs hypothesis + 5-lap test.
8. **Corrections:** if an earlier cue was wrong, say it plainly once.
9. Plain words over jargon; tables only for short comparisons.

Method authority: `docs/coach/telemetry-analysis-playbook.md`.

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
