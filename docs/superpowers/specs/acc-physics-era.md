# ACC physics era map

This project treats **Assetto Corsa Competizione** setup knowledge as **versioned**. The canonical machine-readable map lives at `ac_app/config/acc/physics_era_map.json` (verified on **1.10.3**).

## Eras

| Era | ACC versions | Coaching use |
|-----|----------------|----------------|
| **Pre-1.9** | &lt; 1.9.0 | **Never primary.** Historical context only; legacy hot-pressure meta is obsolete. |
| **1.9** | 1.9.0 – 1.9.x | **Supported baseline.** Kunos **tyre physics rewrite** — dry hot band **26–27 psi**, wet **30–31 psi**, operating temps **~70–100 °C**. |
| **1.10** | ≥ 1.10.0 | **Current.** Adds **damper model / garage fidelity** improvements; 4-way dampers remain first-class levers alongside the 1.9 tyre model. |

## Doctrine

- **Pace-first:** Recommendations must tie to stint pace and telemetry, not forum target numbers from old builds.
- **Reject pre-1.9 pressure dogma:** Advice citing ~27.5–29 psi hot or “pre-1.9 meta” without the **26–27** window should be filtered (`kb_loader.reject_pre_19_advice`).

## References (Kunos changelog themes)

1. **ACC 1.9 — tyre rewrite:** Community and Kunos notes document a full tyre simulation refresh; post-1.9 pressure and heating targets supersede pre-1.9 spreadsheets.
2. **ACC 1.10 — damper improvements:** Damper behaviour and setup application refined; coach damper guidance should assume **1.10+** when citing histogram-style evidence.

## Related files

- `ac_app/config/acc/gt3_physics_kb.json` — lever → effect → when → telemetry matrix
- `ac_app/config/acc/cars/ferrari_296_gt3.json` — Ferrari 296 GT3 profile (400° lock from 1.9.3 fix)
- `ac_app/config/acc/kb_loader.py` — loaders and staleness / dogma guards