"""Vehicle-dynamics checks and setup-effect reasoning from measured car state (any car, any game).

Inputs are data-derived (``car_state`` from ``vre-rpy analyze``; fingerprint from ``vre-rpy setup``).
Where a magnitude needs a per-car calibration that does not exist yet, the function returns the
direction and mechanism only and says so (``calibrated: False``). Nothing here is "calmer is better":
every effect is phrased as what it does to grip, rotation and time.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

G = 9.81


def braking_balance_check(car_state: Dict[str, Any], fp: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Is one axle slipping more than the other under straight-line braking?

    Braking force ≈ friction(slip) × load. When front and rear run the same slip ratio, the force
    split already follows the (dynamic) load split — both axles near peak together. So the balance
    test is the front share of braking slip against 0.5, not against the load share. Fronts slipping
    more → bias forward of the grip (fronts saturate first: longer stops, less rotation); rears
    slipping more → rearward (more rotation, rear-lock risk). Reported as a test, not a verdict.
    """
    est = ((fp or {}).get("estimated") or {}).get("brake_slip_front_share")
    if not est:
        return None
    slip = est["value"]
    noise = est.get("spread") if est.get("spread") == est.get("spread") else 0.0
    gap = slip - 0.5
    tol = max(0.04, 2 * (noise or 0.0))
    if abs(gap) < tol:
        verdict = "balanced: front and rear slip about equally under braking"
    elif gap > 0:
        verdict = "fronts slip more than rears under braking (bias forward of grip)"
    else:
        verdict = "rears slip more than fronts under braking (bias rearward of grip)"
    return {
        "front_slip_share": round(slip, 3), "tolerance": round(tol, 3), "gap_from_even": round(gap, 3),
        "front_load_share_under_braking": car_state.get("front_share_under_braking"),
        "verdict": verdict,
        "lever": "brake bias" if abs(gap) >= tol else None,
        "direction": ("less front bias" if gap > 0 else "more front bias") if abs(gap) >= tol else None,
        "test": "A/B 2-3 clicks; success = shorter braking distance from the same point and equal or better minimum speed",
        "calibrated": False,
    }


def load_transfer(car_state: Dict[str, Any], lat_g: float) -> Optional[Dict[str, Any]]:
    """Measured lateral load transfer at a given lateral g, split front/rear."""
    m, k, fs = car_state.get("mass_kg"), car_state.get("lat_transfer_per_g"), car_state.get("front_lat_transfer_share")
    if None in (m, k):
        return None
    total_n = m * G * k * lat_g
    out = {"lat_g": lat_g, "total_transfer_n": round(total_n, 0), "fraction_of_weight": round(k * lat_g, 3)}
    if fs is not None:
        out.update({"front_n": round(total_n * fs, 0), "rear_n": round(total_n * (1 - fs), 0)})
    return out


def aero_at(car_state: Dict[str, Any], speed_kmh: float) -> Optional[Dict[str, Any]]:
    c, fs, m = car_state.get("aero_load_coeff_n_per_ms2"), car_state.get("aero_front_share"), car_state.get("mass_kg")
    if c is None:
        return None
    df = c * (speed_kmh / 3.6) ** 2
    out = {"speed_kmh": speed_kmh, "downforce_n": round(df, 0)}
    if m:
        out["downforce_vs_weight"] = round(df / (m * G), 3)
    if fs is not None:
        out["front_share"] = round(fs, 3)
    return out


def crest_effect(expected_dg: float, mass_kg: Optional[float]) -> Dict[str, Any]:
    """Load change over a crest/dip (from track geometry and speed): what it does to grip."""
    frac = expected_dg  # g of vertical acceleration ≈ fraction of static load
    out = {"load_change_fraction": round(frac, 3)}
    if mass_kg:
        out["load_change_n"] = round(frac * mass_kg * G, 0)
    out["meaning"] = ("car goes light: less grip for braking and turning — finish braking before it"
                      if frac < -0.05 else ("car is pressed down: extra grip — a place to brake or put power down"
                                            if frac > 0.05 else "small effect"))
    return out


# Setup levers → mechanism (car-independent). Magnitudes come only from per-car calibration.
MECHANISM = {
    "aRBFront": "front bar stiffer → front axle carries more of the roll load transfer → front grip saturates sooner mid-corner (more understeer), quicker response",
    "aRBRear": "rear bar stiffer → rear axle carries more load transfer → more rotation / oversteer, can cost traction on exit",
    "wheelRate": "spring stiffer → less pitch/roll and ride-height change (aero platform), more load transfer on that axle",
    "brakeBias": "more front bias → fronts lock first; more stable entry, less rotation; less front bias → more rotation, rear lock risk",
    "rearWing": "more wing → more rear downforce and drag: aero balance rearward (less high-speed oversteer, lower top speed)",
    "splitter": "more splitter → more front downforce: aero balance forward",
    "rideHeight": "lower front / higher rear (more rake) → aero balance forward and more total downforce until the floor stalls",
    "preload": "more diff preload → more locking off-throttle: stable entry, can push mid-corner and resist rotation",
    "bumpSlow": "stiffer slow bump → load arrives on that corner more slowly (calmer response, less initial bite)",
    "reboundSlow": "stiffer slow rebound → load leaves that corner more slowly (holds weight longer)",
    "bumpStopWindow": "more bump-stop range → stops engage later (more travel before the stiff stop)",
    "tyrePressure": "higher pressure → smaller contact patch, quicker warm-up; aim for the hot pressure window, not a number of clicks",
}


def setup_effect(field: str, delta: int, sensitivities: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    key = field.split(".")[-1]
    out = {"field": field, "delta_clicks": delta, "mechanism": MECHANISM.get(key, "see FIELD_INFO"), "calibrated": False}
    for s in sensitivities or []:
        if s["field"] == field:
            out.setdefault("predicted", []).append({"item": s["item"], "change": round(s["per_click"] * delta, 4),
                                                    "from_sessions": s["sessions"]})
            out["calibrated"] = True
    return out
