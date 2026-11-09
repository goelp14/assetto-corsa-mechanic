# ac_app/lib/telemetry_archive.py
# Python 3.3 compatible — stdlib only

import json
import os
import threading
import time

SCHEMA_VERSION = 1
CHANNEL_VERSION = 2
DEFAULT_MAX_LAP_SAMPLES = 1200


def _decimate_samples(samples, max_count):
    n = len(samples)
    if n <= max_count:
        return samples
    out = []
    step = float(n) / float(max_count)
    i = 0.0
    while len(out) < max_count:
        idx = int(i)
        if idx >= n:
            break
        out.append(samples[idx])
        i += step
    return out


def _add_car_channels(sample, frame):
    """Per-wheel channels (FL, FR, RL, RR) needed to tune pressures, camber, diff and ride height."""
    slip = getattr(frame, "slip", ())
    if any(slip):
        sample["wheel_slip"] = [round(v, 3) for v in slip]
    ws = getattr(frame, "wheel_speed", ())
    if any(ws):
        sample["wheel_rads"] = [round(v, 2) for v in ws]
    core = getattr(frame, "tyre_temp", ())
    if any(core):
        sample["tyre_core"] = [round(v, 1) for v in core]
    psi = getattr(frame, "tyre_pressure", ())
    if any(psi):
        sample["tyre_psi"] = [round(v, 2) for v in psi]
    imo = getattr(frame, "tyre_temp_imo", ())
    if imo:
        sample["tyre_imo"] = [[round(v, 1) for v in t] for t in imo]
    camber = getattr(frame, "camber", ())
    if any(camber):
        sample["camber_deg"] = [round(v * 57.2958, 2) for v in camber]
    bt = getattr(frame, "brake_temp", ())
    if bt:
        sample["brake_temp"] = [round(v, 0) for v in bt]
    rh = getattr(frame, "ride_height", ())
    if rh:
        sample["ride_height_mm"] = [round(v * 1000.0, 1) for v in rh]


def _mean(vals):
    return sum(vals) / float(len(vals)) if vals else 0.0


def _lap_car_summary(samples):
    """Per-wheel lap averages; tyre temps only while cornering, where the contact patch matters."""
    out = {}
    psi = [s["tyre_psi"] for s in samples if "tyre_psi" in s]
    if psi:
        out["psi_mean"] = [round(_mean([p[i] for p in psi]), 2) for i in range(4)]
        out["psi_max"] = [round(max(p[i] for p in psi), 2) for i in range(4)]
    core = [s["tyre_core"] for s in samples if "tyre_core" in s]
    if core:
        out["core_mean"] = [round(_mean([c[i] for c in core]), 1) for i in range(4)]
    loaded = [s for s in samples if abs(s.get("acc_g_lat", 0.0)) > 0.8 and "tyre_imo" in s]
    if loaded:
        out["imo_cornering"] = [
            [round(_mean([s["tyre_imo"][i][k] for s in loaded]), 1) for k in range(3)] for i in range(4)
        ]
    cam = [s for s in samples if abs(s.get("acc_g_lat", 0.0)) > 0.8 and "camber_deg" in s]
    if cam:
        out["camber_cornering_deg"] = [round(_mean([s["camber_deg"][i] for s in cam]), 2) for i in range(4)]
    bt = [s["brake_temp"] for s in samples if "brake_temp" in s]
    if bt:
        out["brake_temp_max"] = [round(max(b[i] for b in bt), 0) for i in range(4)]
    rh = [s["ride_height_mm"] for s in samples if "ride_height_mm" in s]
    if rh:
        out["ride_height_min_mm"] = [round(min(r[i] for r in rh), 1) for i in range(2)]
    susp = [s["susp_ratio"] for s in samples if "susp_ratio" in s]
    if susp:
        out["bump_stop_pct"] = [round(100.0 * sum(1 for r in susp if r[i] > 0.97) / len(susp), 1) for i in range(4)]
    if samples:
        out["top_speed_kmh"] = max(s.get("speed_kmh", 0.0) for s in samples)
        out["max_rpm"] = max(s.get("rpm", 0) for s in samples)
    return out


class TelemetryArchive(object):
    """JSONL session logs and per-lap subsampled telemetry."""

    def __init__(self, sessions_dir=None, subsample_every=6, max_lap_samples=DEFAULT_MAX_LAP_SAMPLES,
                 async_writes=True):
        self.sessions_dir = sessions_dir
        self.subsample_every = max(1, int(subsample_every))
        self.max_lap_samples = max(100, int(max_lap_samples))
        self.async_writes = async_writes
        self.session_dir = None
        self.session_id = ""
        self._jsonl_path = None
        self._frame_counter = 0
        self._tyres_out_peak = 0
        self._reset_lap_ffb()
        self._lap_samples = []
        self._lap_corner_summaries = []
        self._feedback_counter = 0
        self._io_lock = threading.Lock()
        self._pending_writes = 0
        self._phase = "LEARNING"
        self._setup_tweaks_applied = 0
        self._setup_tweaks_reverted = 0

    def _base_dir(self):
        if self.sessions_dir is not None:
            return self.sessions_dir
        return os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "sessions",
        )

    def start_session(self, track, car, phase="LEARNING", baseline_setup="", track_config=""):
        ts = time.strftime("%Y-%m-%d_%H%M%S")
        ms = int((time.time() % 1.0) * 1000)
        safe_track = track.replace(" ", "_").lower() or "unknown"
        self.session_id = "%s_%03d_%s" % (ts, ms, safe_track)
        self._phase = phase
        self._setup_tweaks_applied = 0
        self._setup_tweaks_reverted = 0
        self.session_dir = os.path.join(self._base_dir(), self.session_id)
        laps_dir = os.path.join(self.session_dir, "laps")
        if not os.path.isdir(laps_dir):
            os.makedirs(laps_dir)
        self._jsonl_path = os.path.join(self.session_dir, "session.jsonl")
        readme = os.path.join(self.session_dir, "README.txt")
        with open(readme, "w") as fh:
            fh.write(
                "Virtual Race Engineer session\n"
                "Track: %s\nLayout: %s\nCar: %s\nStarted: %s\n"
                % (track, track_config or "-", car, ts)
            )
        self.append_record({
            "record_type": "session_start",
            "schema_version": SCHEMA_VERSION,
            "timestamp": self._iso_now(),
            "track": track,
            "track_config": track_config,
            "car": car,
            "phase": phase,
            "baseline_setup": baseline_setup,
            # 2 = acc_g remapped to (long, lat, vert), heading-derived yaw rate,
            # body velocity from world x/z; sessions without it have bad dynamics channels.
            "channel_version": CHANNEL_VERSION,
        })

    def _iso_now(self):
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def append_record(self, record):
        if self._jsonl_path is None:
            return
        if "timestamp" not in record:
            record["timestamp"] = self._iso_now()
        if "schema_version" not in record:
            record["schema_version"] = SCHEMA_VERSION
        line = json.dumps(record, separators=(",", ":")) + "\n"
        with self._io_lock:
            with open(self._jsonl_path, "a") as fh:
                fh.write(line)

    def observe_frame(self, frame, corner="", phase="", dynamics=None, balance=None):
        self._frame_counter += 1
        # Kerb hops can be shorter than the subsample interval, so keep the peak between samples.
        self._tyres_out_peak = max(self._tyres_out_peak, getattr(frame, "tyres_out", 0))
        ffb = abs(getattr(frame, "ffb", 0.0) or 0.0)
        if ffb > 0.0:
            self._ffb_peak = max(self._ffb_peak, ffb)
            self._ffb_frames += 1
            if ffb >= 0.99:
                self._ffb_clip_frames += 1
        if getattr(frame, "brake_bias", 0.0):
            self._brake_bias = frame.brake_bias
        if self._frame_counter % self.subsample_every != 0:
            return
        sample = {
            "spline": round(frame.spline, 4),
            "corner": corner,
            "phase": phase,
            "speed_kmh": round(frame.speed_kmh, 1),
            "brake": round(frame.brake, 3),
            "throttle": round(frame.throttle, 3),
            "steer_deg": round(frame.steer * 57.2958, 2),
            "steer_road_deg": round(getattr(frame, "steer_road", 0.0) * 57.2958, 2),
            "acc_g_lat": round(frame.acc_g[1], 3),
            "acc_g_long": round(frame.acc_g[0], 3),
            "pos_x": round(frame.pos_x, 2),
            "pos_z": round(frame.pos_z, 2),
            "heading": round(frame.heading, 4),
        }
        if dynamics is not None:
            import math
            beta = math.degrees(dynamics.beta)
            if beta > 90.0:
                beta = 90.0
            elif beta < -90.0:
                beta = -90.0
            sample["beta_deg"] = round(beta, 2)
            sample["yaw_rate"] = round(frame.yaw_rate, 4)
        if balance is not None and balance.valid:
            import math
            sample["delta_us_deg"] = round(math.degrees(balance.delta_us), 2)
        if getattr(frame, "gear", 0) > 0:
            sample["gear"] = int(frame.gear)
            sample["rpm"] = int(getattr(frame, "rpm", 0))
        if any(frame.wheel_load):
            sample["wheel_load"] = [round(v, 0) for v in frame.wheel_load]
        if any(frame.susp_ratio):
            sample["susp_ratio"] = [round(v, 3) for v in frame.susp_ratio]
        _add_car_channels(sample, frame)
        if any(getattr(frame, "tyre_radius", ())):
            self._tyre_radius = frame.tyre_radius
        if self._tyres_out_peak:
            sample["tyres_out"] = self._tyres_out_peak
            self._tyres_out_peak = 0
        if self._ffb_peak:
            sample["ffb"] = round(self._ffb_peak, 3)
            self._ffb_peak = 0.0
        self._lap_samples.append(sample)

    def record_investigation(self, lap, corner, phase, investigation, feedback_id=None):
        """Persist CornerInvestigator output for offline replay viewer."""
        if investigation is None:
            return
        ev = dict(investigation.evidence or {})
        self.append_record({
            "record_type": "investigation",
            "lap": lap,
            "corner": corner,
            "phase": phase,
            "template_key": investigation.template_key,
            "root_cause_id": investigation.root_cause_id,
            "confidence": investigation.confidence,
            "evidence": ev,
            "feedback_id": feedback_id,
        })

    def record_corner_event(self, lap, corner, phase, verdict, input_score,
                            output_score, evidence=None, feedback_id=None):
        self._lap_corner_summaries.append({
            "corner": corner,
            "phase": phase,
            "verdict": verdict,
            "peak_ay_g": evidence.get("peak_ay_g", 0) if evidence else 0,
            "mean_delta_us_deg": evidence.get("mean_delta_us_deg", 0) if evidence else 0,
            "time_delta_s": evidence.get("time_delta_s", 0) if evidence else 0,
        })
        self.append_record({
            "record_type": "corner_event",
            "lap": lap,
            "corner": corner,
            "phase": phase,
            "verdict": verdict,
            "input_score": input_score,
            "output_score": output_score,
            "evidence": evidence or {},
            "feedback_id": feedback_id,
        })

    def record_feedback(self, event):
        self._feedback_counter += 1
        fb_id = "fb_%03d" % self._feedback_counter
        self.append_record({
            "record_type": "feedback",
            "feedback_id": fb_id,
            "type": event.type,
            "headline": event.headline,
            "action": event.action,
            "voice": event.voice,
        })
        return fb_id

    def _write_lap_files(self, lap_path, payload, summary):
        try:
            with open(lap_path, "w") as fh:
                json.dump(payload, fh, separators=(",", ":"))
                fh.write("\n")
            self.append_record(summary)
        finally:
            self._pending_writes -= 1

    def record_phase_change(self, from_phase, to_phase, lap, clean_laps=0, total_laps=0):
        self._phase = to_phase
        self.append_record({
            "record_type": "phase_change",
            "from_phase": from_phase,
            "to_phase": to_phase,
            "lap": lap,
            "clean_laps": int(clean_laps),
            "total_laps": int(total_laps),
        })

    def record_pit_transition(self, kind, lap, spline=0.0):
        self.append_record({
            "record_type": "pit_transition",
            "kind": kind,
            "lap": lap,
            "spline": round(float(spline), 4),
        })

    def record_shift_event(self, event):
        if event is None:
            return
        payload = event.to_dict() if hasattr(event, "to_dict") else event
        payload["record_type"] = "shift_event"
        self.append_record(payload)

    def note_setup_tweak(self, count=1):
        self._setup_tweaks_applied += int(count)

    def note_setup_revert(self, count=1):
        self._setup_tweaks_reverted += int(count)

    def _reset_lap_ffb(self):
        self._ffb_peak = 0.0
        self._ffb_frames = 0
        self._ffb_clip_frames = 0
        self._brake_bias = 0.0
        self._tyre_radius = (0.0, 0.0, 0.0, 0.0)

    def _live_car_state(self):
        out = {}
        if any(self._tyre_radius):
            out["tyre_radius_m"] = [round(v, 4) for v in self._tyre_radius]
        if self._ffb_frames:
            out["ffb_clip_pct"] = round(100.0 * self._ffb_clip_frames / self._ffb_frames, 1)
        if self._brake_bias:
            out["brake_bias_live"] = round(100.0 * self._brake_bias, 1)
        return out

    def flush_lap(self, lap, lap_time_ms, setup_snapshot=None, driving_style=None,
                  corner_deltas=None, sector_deltas=None, lap_type="flying",
                  phase="", in_pit=False, counted=True, setup_source=""):
        if self.session_dir is None:
            return

        samples = _decimate_samples(self._lap_samples, self.max_lap_samples)
        live = self._live_car_state()
        payload = {
            "lap": lap,
            "lap_time_ms": lap_time_ms,
            "lap_type": lap_type,
            "counted": counted,
            "sample_count_raw": len(self._lap_samples),
            "tyres_out_tracked": True,
            "samples": samples,
            "corner_summaries": list(self._lap_corner_summaries),
        }
        car_state = _lap_car_summary(samples)
        if car_state:
            live["car_state"] = car_state
        payload.update(live)
        self._lap_samples = []
        self._lap_corner_summaries = []
        self._frame_counter = 0
        self._tyres_out_peak = 0
        self._reset_lap_ffb()

        summary = {
            "record_type": "lap_summary",
            "lap": lap,
            "lap_time_ms": lap_time_ms,
            "lap_type": lap_type,
            "counted": counted,
            "phase": phase or self._phase,
            "in_pit": bool(in_pit),
        }
        summary.update(live)
        if setup_snapshot:
            summary["setup_snapshot"] = setup_snapshot
            if setup_source:
                summary["setup_snapshot_source"] = setup_source
        if driving_style:
            summary["driving_style"] = driving_style
        if corner_deltas:
            summary["corner_deltas_s"] = corner_deltas
        if sector_deltas:
            summary["sector_deltas_s"] = sector_deltas
        if driving_style and driving_style.get("shift_summary"):
            summary["shift_summary"] = driving_style.get("shift_summary")

        lap_path = os.path.join(self.session_dir, "laps", "lap_%02d.json" % lap)
        if self.async_writes:
            self._pending_writes += 1
            thread = threading.Thread(
                target=self._write_lap_files,
                args=(lap_path, payload, summary),
            )
            thread.daemon = True
            thread.start()
        else:
            self._write_lap_files(lap_path, payload, summary)

    def record_setup_change(self, tweak_id, parameter, old_value, new_value,
                            symptom="", reason="", **context):
        record = {
            "record_type": "setup_change",
            "tweak_id": tweak_id,
            "parameter": parameter,
            "old_value": old_value,
            "new_value": new_value,
            "symptom": symptom,
            "reason": reason,
        }
        for key in (
            "lap", "corner", "corner_display", "phase", "spline", "verdict",
            "input_score", "output_score", "corner_delta_s", "detection_what",
            "detection_why", "source", "queued_lap", "pit_entry", "delta",
        ):
            if key in context and context[key] is not None:
                record[key] = context[key]
        self.append_record(record)

    def record_session_plan(self, items, potential_gap_s=0.0):
        self.append_record({
            "record_type": "session_plan",
            "potential_gap_s": round(float(potential_gap_s), 3),
            "items": items,
        })

    def end_session(self, total_laps, best_lap_ms, tweaks_applied=0, tweaks_reverted=0,
                    phase="LEARNING"):
        if tweaks_applied <= 0:
            tweaks_applied = self._setup_tweaks_applied
        if tweaks_reverted <= 0:
            tweaks_reverted = self._setup_tweaks_reverted
        self.append_record({
            "record_type": "session_end",
            "total_laps": total_laps,
            "best_lap_ms": best_lap_ms,
            "phase": phase or self._phase,
            "setup_tweaks_applied": tweaks_applied,
            "setup_tweaks_reverted": tweaks_reverted,
        })
