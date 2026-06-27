---
name: vre-teach-answer
description: Use when formatting the final driver-facing coaching response from collected evidence.
---

# VRE Teach Answer

Format evidence into actionable coaching copy.

## Output template

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
- Pair WHAT (awareness) + HOW (mental image)
- No motivational filler

## Validation

Before sending:

1. Every number appears in evidence pack
2. Every citation_id exists in pack
3. If confidence < 0.6, say "insufficient evidence" and name missing channel

**REQUIRED SUB-SKILL:** Use `verification-before-completion`

## Deterministic fallback

If no LLM key: use `python -m external.query_tools.coach ask` — returns rule-based response from incidents/corner_reports.
