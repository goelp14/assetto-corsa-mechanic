# VRE Replay Viewer

React + uPlot viewer for exported stint bundles under `exports/`.

## Build (usually automatic)

From repo root, `./replay.sh` builds this package on first run if `dist/` is missing.

Manual:

```bash
cd replay-viewer
npm install
npm run build
```

Dev server with hot reload:

```bash
npm run dev
```

Serve exports via the main launcher (`../replay.sh`) — it proxies `/bundles/` and `/api/sessions`.

## Features

- Track map with corner regions and coaching pins
- Distance-synced telemetry charts (speed, inputs, G, steering)
- Map ↔ chart region zoom (Shift+drag or Select region)
- Lap compare overlay, time-loss panel, stint narrative
- Coach notes layer and optional coach chat (`VRE_COACH=1`)

See [../docs/USAGE.md](../docs/USAGE.md) for the full workflow.
