# Coaching Rubric

Rules for evidence-grounded coaching responses.

## Response structure

Every answer must include:

1. **WHAT** — cite metric from evidence (`evidence_id`)
2. **WHY** — mechanism in plain language (tyre load, grip envelope)
3. **HOW** — exactly one drill

Optional: **summary** (2 sentences max), **confidence** (0–1).

## Confidence thresholds

| Confidence | When |
|------------|------|
| ≥ 0.8 | Incident pre-window + hypothesis + reference delta |
| 0.6–0.8 | Corner report or time loss with phase metrics |
| < 0.6 | Say "insufficient evidence" — suggest which chart to inspect |

## When to refuse

- No citations in evidence pack for scoped corner/lap
- Question asks about setup but verdict is `NONE` (spin) — say driver input, not setup
- Missing `beta_deg` in archive — cannot diagnose spin offline; say so

## Citation rules

- Every number in the response must appear in the evidence pack
- Use `evidence_id` from pack (`incident_0`, `corner_3`, etc.)
- Never invent lap times or corner names not in manifest

## Templates

Map to `ac_app/config/feedback_templates.json`:

- `root_loss_of_control` — spin / high beta
- `root_exit_throttle` — power too early on exit
- `root_throttle_lateral` — power while turning
- `root_entry_overspeed` — entry too fast
