# Replay viewer

React + uPlot viewer for bundles under `exports/`.

**Users:** run `./replay.sh` from repo root — see [docs/USAGE.md](../docs/USAGE.md).

**Dev:**

```bash
npm install && npm run dev    # hot reload
npm run build                 # production dist/
```

The launcher serves `dist/` and proxies `/bundles/` and `/api/sessions`.
