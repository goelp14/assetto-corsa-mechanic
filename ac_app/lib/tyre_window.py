# ac_app/lib/tyre_window.py
# Python 3.3 compatible — stdlib only

import json
import os

TYRE_NAMES = ("LF", "RF", "LR", "RR")


def _trimmed_mean(values, trim_frac=0.1):
    if not values:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    cut = int(n * trim_frac)
    if cut * 2 >= n:
        core = ordered
    else:
        core = ordered[cut:n - cut]
    return sum(core) / float(len(core))


class TyreSampleState(object):
    __slots__ = ("temps", "pressures", "slips", "skipped")

    def __init__(self):
        self.temps = []
        self.pressures = []
        self.slips = []
        self.skipped = 0

    def observe(self, temp_c, pressure_psi, slip, max_samples=300):
        if len(self.temps) >= max_samples:
            return
        self.temps.append(temp_c)
        self.pressures.append(pressure_psi)
        self.slips.append(slip)

    def skip(self):
        self.skipped += 1

    def sample_count(self):
        return len(self.temps)

    def mean_temp(self):
        return _trimmed_mean(self.temps)

    def mean_pressure(self):
        return _trimmed_mean(self.pressures)

    def mean_slip(self):
        return _trimmed_mean(self.slips)


class TyreDiagnosis(object):
    __slots__ = ("symptom", "tyre", "axle", "evidence", "priority")

    def __init__(self, symptom, tyre="", axle="", evidence=None, priority=2):
        self.symptom = symptom
        self.tyre = tyre
        self.axle = axle
        self.evidence = evidence or {}
        self.priority = priority


class TyreWindowTracker(object):
    """Track core temps with spike rejection and stint-level tyre window diagnosis."""

    def __init__(self, config_path=None, thresholds=None):
        self.thresholds = thresholds or {}
        self._config = self._load_config(config_path)
        self._compound = "default"
        self._windows = dict(self._config.get("default", {}))
        self._tyres = [TyreSampleState() for _ in range(4)]
        self._stint_history = [[] for _ in range(4)]
        self._lap_slip_sum = 0.0
        self._lap_slip_n = 0
        self._lap_steer_sum = 0.0
        self._lap_steer_n = 0
        self._lap_incidents = 0
        self._lap_valid_samples = 0
        self._last_summary = {}

    @classmethod
    def default_config_path(cls):
        return os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config", "tyre_windows.json",
        )

    def _load_config(self, path):
        cfg_path = path or self.default_config_path()
        with open(cfg_path, "r") as fh:
            return json.load(fh)

    def set_compound(self, compound_name):
        if not compound_name:
            return
        key = compound_name.strip().lower()
        base = dict(self._config.get("default", {}))
        overrides = self._config.get("compounds", {}).get(key, {})
        base.update(overrides)
        self._compound = key
        self._windows = base

    def _window(self, key, default):
        return float(self._windows.get(key, default))

    def _thresh(self, key, default):
        return float(self.thresholds.get(key, default))

    def _running_temp_hint(self, idx):
        st = self._tyres[idx]
        if st.sample_count() < 5:
            return None
        return st.mean_temp()

    def _is_spike_sample(self, temps, slips, yaw_rate):
        spike_slip = self._window(
            "spike_slip_threshold",
            self._thresh("TYRE_SPIKE_SLIP", 0.22),
        )
        mean_slip = sum(slips) / 4.0
        if mean_slip >= spike_slip:
            return True
        if abs(yaw_rate) >= self._thresh("YAW_ACCEL_CRITICAL", 2.0) * 0.75:
            return True
        spike_delta = self._thresh("TYRE_SPIKE_TEMP_DELTA_C", 18.0)
        for i, temp in enumerate(temps):
            hint = self._running_temp_hint(i)
            if hint is not None and temp > hint + spike_delta:
                return True
        return False

    def observe(self, frame):
        if frame.speed_kmh < self._window("min_sample_speed_kmh", 40.0):
            return
        if abs(frame.acc_g[1]) < self._window("min_sample_ay_g", 0.15):
            if frame.throttle < 0.2 and frame.brake < 0.1:
                return

        temps = frame.tyre_temp
        pressures = frame.tyre_pressure
        slips = frame.slip
        ay = frame.acc_g[1]
        yaw_rate = getattr(frame, "yaw_rate", 0.0)

        if self._is_spike_sample(temps, slips, yaw_rate):
            self._lap_incidents += 1
            for st in self._tyres:
                st.skip()
            return

        self._lap_valid_samples += 1
        for i in range(4):
            self._tyres[i].observe(temps[i], pressures[i], slips[i])

        mean_slip = sum(slips) / 4.0
        self._lap_slip_sum += mean_slip
        self._lap_slip_n += 1
        self._lap_steer_sum += abs(frame.steer)
        self._lap_steer_n += 1

    def driving_style(self):
        aggression = 0.0
        if self._lap_slip_n > 0:
            mean_slip = self._lap_slip_sum / float(self._lap_slip_n)
            aggression += min(1.0, mean_slip / 0.12)
        if self._lap_steer_n > 0:
            mean_steer = self._lap_steer_sum / float(self._lap_steer_n)
            aggression += min(1.0, mean_steer / 0.25)
        aggression = aggression / 2.0
        return {
            "aggression": aggression,
            "consistency": 1.0 - min(1.0, aggression * 0.6),
            "slip_index": self._lap_slip_sum / float(self._lap_slip_n) if self._lap_slip_n else 0.0,
        }

    def _lap_is_representative(self):
        if self._lap_valid_samples < 15:
            return False
        total = float(self._lap_valid_samples + self._lap_incidents)
        if total <= 0:
            return False
        return float(self._lap_incidents) / total < 0.20

    def _stint_temp(self, idx):
        history = self._stint_history[idx]
        if len(history) >= int(self._thresh("TYRE_STINT_LAPS_MIN", 2)):
            recent = history[-3:]
            return sum(recent) / float(len(recent))
        st = self._tyres[idx]
        if st.sample_count() >= 10:
            return st.mean_temp()
        return None

    def stint_ready(self):
        min_laps = int(self._thresh("TYRE_STINT_LAPS_MIN", 2))
        if not self._stint_history[0]:
            return False
        return len(self._stint_history[0]) >= min_laps

    def _classify_temp(self, temp):
        hot = self._window("core_temp_hot_c", 102.0)
        cold = self._window("core_temp_cold_c", 68.0)
        ideal_lo = self._window("core_temp_ideal_min_c", 75.0)
        ideal_hi = self._window("core_temp_ideal_max_c", 95.0)

        if temp >= hot:
            return "hot"
        if temp <= cold:
            return "cold"
        if temp > ideal_hi:
            return "warm"
        if temp < ideal_lo:
            return "cool"
        return "ideal"

    def _symptom_for(self, state, axle, style):
        agg = style.get("aggression", 0.0)
        if state in ("hot", "warm"):
            if axle == "front" and agg >= 0.55:
                return "tyre_front_hot_aggressive"
            if axle == "rear" and agg >= 0.55:
                return "tyre_rear_hot_aggressive"
            if axle == "front":
                return "tyre_front_hot"
            return "tyre_rear_hot"
        if state in ("cold", "cool"):
            if agg < 0.4:
                return "tyre_%s_cold_conservative" % axle
            return "tyre_%s_cold" % axle
        return None

    def finish_lap(self):
        style = self.driving_style()
        representative = self._lap_is_representative()
        diagnoses = []
        summary = {
            "compound": self._compound,
            "tyres": {},
            "style": style,
            "lap_representative": representative,
            "stint_ready": False,
        }
        stint_cap = int(self._window("stint_history_laps", 4))

        for i, name in enumerate(TYRE_NAMES):
            st = self._tyres[i]
            lap_temp = st.mean_temp() if st.sample_count() else 0.0
            stint_temp = self._stint_temp(i)
            display_temp = stint_temp if stint_temp is not None else lap_temp

            if representative and st.sample_count() >= 10:
                self._stint_history[i].append(lap_temp)
                if len(self._stint_history[i]) > stint_cap:
                    self._stint_history[i] = self._stint_history[i][-stint_cap:]

            state = self._classify_temp(display_temp) if display_temp > 0 else None
            summary["tyres"][name] = {
                "samples": st.sample_count(),
                "skipped_spikes": st.skipped,
                "lap_temp_c": round(lap_temp, 1),
                "stint_temp_c": round(display_temp, 1) if display_temp else 0.0,
                "mean_temp_c": round(display_temp, 1) if display_temp else 0.0,
                "mean_pressure_psi": round(st.mean_pressure(), 2),
                "mean_slip": round(st.mean_slip(), 4),
                "state": state or "unknown",
            }

            if not representative or not self.stint_ready():
                continue
            if state is None or state == "ideal":
                continue
            axle = "front" if i < 2 else "rear"
            symptom = self._symptom_for(state, axle, style)
            if symptom:
                diagnoses.append(TyreDiagnosis(
                    symptom, tyre=name, axle=axle,
                    evidence={
                        "mean_temp_c": display_temp,
                        "lap_temp_c": lap_temp,
                        "mean_pressure_psi": st.mean_pressure(),
                        "mean_slip": st.mean_slip(),
                        "aggression": style.get("aggression", 0.0),
                        "compound": self._compound,
                        "stint_laps": len(self._stint_history[i]),
                    },
                    priority=3 if state in ("hot", "cold") else 2,
                ))

        if representative and self.stint_ready() and not diagnoses:
            for axle, indices in (("front", (0, 1)), ("rear", (2, 3))):
                temps = []
                for idx in indices:
                    stint_temp = self._stint_temp(idx)
                    if stint_temp is not None:
                        temps.append(stint_temp)
                if not temps:
                    continue
                avg = sum(temps) / float(len(temps))
                state = self._classify_temp(avg)
                if state in ("hot", "cold"):
                    symptom = self._symptom_for(state, axle, style)
                    if symptom:
                        diagnoses.append(TyreDiagnosis(
                            symptom, axle=axle,
                            evidence={
                                "mean_temp_c": avg,
                                "aggression": style.get("aggression", 0.0),
                                "stint_laps": len(self._stint_history[indices[0]]),
                            },
                            priority=2,
                        ))

        diagnoses.sort(key=lambda d: d.priority, reverse=True)
        summary["stint_ready"] = self.stint_ready()
        self._last_summary = summary
        self._reset_lap_accumulators()
        return diagnoses

    def _reset_lap_accumulators(self):
        self._tyres = [TyreSampleState() for _ in range(4)]
        self._lap_slip_sum = 0.0
        self._lap_slip_n = 0
        self._lap_steer_sum = 0.0
        self._lap_steer_n = 0
        self._lap_incidents = 0
        self._lap_valid_samples = 0

    def last_summary(self):
        return self._last_summary

    def ideal_temp_range(self):
        return (
            int(self._window("core_temp_ideal_min_c", 75.0)),
            int(self._window("core_temp_ideal_max_c", 95.0)),
        )

    def temp_thresholds(self):
        lo, hi = self.ideal_temp_range()
        return {
            "ideal_lo": lo,
            "ideal_hi": hi,
            "hot_c": int(self._window("core_temp_hot_c", 102.0)),
            "cold_c": int(self._window("core_temp_cold_c", 68.0)),
        }
