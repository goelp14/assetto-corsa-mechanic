---
name: vre-coach-router
description: Use when the user asks about lap telemetry, spins, corner technique, stint debrief, or why something happened on track.
---

# VRE Coach Router

Entry point for telemetry coaching questions.

## Workflow

1. Parse intent: incident (spin), technique (time loss), mechanism (physics), stint (summary)
2. Resolve bundle path: `exports/<session_id>/` or run `./replay.sh` to sync
3. Extract scope: corner id, lap number, spline if mentioned

**REQUIRED SUB-SKILL:** Use `vre-collect-evidence`

Then delegate by intent:

| Intent | Sub-skill |
|--------|-----------|
| spin, crash, lost control | `vre-incident-analysis` |
| technique, drill, time loss | `vre-corner-coaching` |
| understeer, grip, why mechanism | `vre-explain-dynamics` |
| stint summary | `vre-corner-coaching` |

**REQUIRED SUB-SKILL:** Use `vre-teach-answer` for final response.

After lap-specific coaching, **persist notes on the replay**:

**REQUIRED SUB-SKILL:** Use `vre-annotate-replay`

## CLI

```bash
python -m external.query_tools.coach ask \
  --bundle exports/<session_id> \
  --question "<user question>" \
  --corner <id> --lap <n>
```

Read [CONTEXT.md](../../CONTEXT.md) for domain terms.
