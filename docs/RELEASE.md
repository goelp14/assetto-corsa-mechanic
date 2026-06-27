# Releases

GitHub Actions builds and publishes release assets when you push a version tag.

## Cost

For public repositories, **GitHub Actions and Releases are free** (within generous usage limits). Private repos get 2,000 Actions minutes/month on the free plan — this project’s workflows typically use a few minutes per run.

## What each release includes

| Asset | Use |
|-------|-----|
| `VirtualRaceEngineer.zip` | Drag onto **Content Manager** to install the in-game app |
| `replay-viewer-dist.zip` | Pre-built replay viewer static files (optional; `./replay.sh` builds locally) |
| `SHA256SUMS` | Verify downloads |

## Cut a release

1. Ensure `main` is green (CI workflow).
2. Choose a version (matches `pyproject.toml`, e.g. `0.1.0`).
3. Tag and push:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The **Release** workflow runs tests, builds both packages, and creates a GitHub Release with assets attached.

## Install from a release (no git clone)

1. Open [GitHub Releases](https://github.com/goelp14/assetto-corsa-mechanic/releases).
2. Download `VirtualRaceEngineer.zip` from the latest tag.
3. Drag the zip onto **Content Manager** (or **Content → Install**).
4. Enable **Virtual Race Engineer** under CM → Settings → Assetto Corsa → Apps.

For replay analysis, clone the repo and run `./replay.sh`, or extract `replay-viewer-dist.zip` and serve the folder with any static file server (the full launcher expects `exports/` from `./replay.sh`).

## CI (every push to main)

The **CI** workflow runs on pushes and pull requests:

- `pytest` (122+ tests)
- Replay viewer `npm run build`
- Smoke test that `VirtualRaceEngineer.zip` packages correctly
