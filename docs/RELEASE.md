# Releases

For maintainers. End users: download from [GitHub Releases](https://github.com/goelp14/assetto-corsa-mechanic/releases) and follow [INSTALL.md](INSTALL.md).

## Assets per release

| Asset | Purpose |
|-------|---------|
| `VirtualRaceEngineer.zip` | In-game app — drag onto Content Manager |
| `replay-viewer-dist.zip` | Pre-built viewer static files (optional; `./replay.sh` builds locally) |
| `SHA256SUMS` | Verify downloads |

## Cut a release

1. Ensure `main` CI is green
2. Match version in `pyproject.toml` (e.g. `0.1.0`)
3. Tag and push:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The **Release** workflow runs tests, builds packages, and attaches assets.

## CI (every push / PR)

- `pytest`
- Replay viewer `npm run build`
- Smoke test that `VirtualRaceEngineer.zip` packages correctly

Public repos: GitHub Actions and Releases are free within standard limits.
