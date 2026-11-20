# ACC fallback ingest

When the in-game VRE app is not attached, ACC sessions can still reach the coach pipeline via two paths:

## Shared memory logger (`acc_shm`)

Windows-only while ACC is running. Polls `Local\acpmf_physics`, `Local\acpmf_graphics`, and `Local\acpmf_static` at ~50 Hz and writes a normal VRE session under `data/sessions_acc/` (override with `--out`).

```bash
python -m external.query_tools.acc_ingest.shm_logger --hz 50 --steering-lock 400
```

- `session_start`: `game=acc`, `source=acc_shm`, track and car from static SHM.
- Laps flush when `completedLaps` increases; lap time from `iLastTime`.
- Samples include spline (`normalizedCarPosition`), inputs, G, heading, tyre core/psi, TC/ABS intervention floats, plus graphics TC/TCCut/ABS/EngineMap levels on the raw side before normalize.

If mappings are missing, the logger waits and retries (no crash loop).

## MoTeC `.ld` import (`acc_motec`)

Offline import from ACC’s MoTeC export:

```bash
python -m external.query_tools.acc_ingest.motec_ld path/to/file.ld --out path/to/session_dir
python -m external.query_tools.acc_ingest.motec_ld path/to/file.ld --discover
```

Requires [gotzl/ldparser](https://github.com/gotzl/ldparser) and **numpy** on `PYTHONPATH` (not on PyPI as a package). `--discover` lists channels; without ldparser the command exits with install instructions.

Channel mapping is case-insensitive and covers ACC Epic MoTeC names (`SPEED`, `THROTTLE`, `BRAKE`, `STEERANGLE`, `GEAR`, `RPMS`, `LAP_BEACON`, `TIME`, `G_LAT`/`G_LON`, `TC`/`ABS`, tyre pressures/temps) plus generic aliases. When Lap Distance is missing, spline is integrated from `SPEED×TIME` (pass `--track-length-m`, or auto 7004/5793 for spa/monza).

## Shared normalization

`external/query_tools/acc_ingest/normalize.py` is the single writer for `acc_rpy`, `acc_shm`, and `acc_motec`:

- `write_session_start` / `write_lap`
- `normalize_sample` → schema-aligned lap samples (`channel_version` 2 on session start)

Track configs for ACC naming: `ac_app/config/tracks/monza_acc.json`, `spa_acc.json`.