# ac_app/lib/corner_investigator.py
# Evidence-based root-cause diagnosis for driver coaching (Python 3.3).

"""
Protocol:
  1. OBSERVE — phase metrics vs personal reference (same car, same track, your data)
  2. HYPOTHESIZE — ranked causes with required evidence thresholds
  3. EXPLAIN — what happened (measurement), why (mechanism), how (one fix)
"""


class InvestigationResult(object):
    __slots__ = ("template_key", "phase", "evidence", "root_cause_id", "confidence")

    def __init__(self, template_key, phase="exit", evidence=None,
                 root_cause_id="", confidence=0.7):
        self.template_key = template_key
        self.phase = phase
        self.evidence = evidence or {}
        self.root_cause_id = root_cause_id
        self.confidence = confidence


class CornerInvestigator(object):
    """Diagnose *why* a corner went wrong using phase telemetry vs your reference."""

    ROOT_LABELS = {
        "exit_throttle_under_load": "Throttle too early on exit",
        "entry_overspeed": "Entry too fast",
        "steer_fight": "Fighting the line",
        "scrubbed_min_speed": "Too much mid-corner speed scrub",
        "throttle_under_lateral": "Power while still turning",
        "loss_of_control_exit": "Exit exceeded grip",
    }

    def __init__(self, thresholds=None):
        self.thresholds = thresholds or {}

    def _t(self, key, default):
        return float(self.thresholds.get(key, default))

    def _phase(self, summary, name):
        if not summary:
            return {}
        return summary.get("phases", {}).get(name, {})

    def _ref_phase(self, reference, name):
        if not reference:
            return {}
        return reference.get("phases", {}).get(name, {})

    def _base_evidence(self, corner, phase, landmarks=None, line_cfg=None):
        ev = {
            "corner": corner,
            "corner_name": corner,
            "phase": phase,
            "map": "",
            "approach": "",
            "brake_cue": "",
            "apex_cue": "",
            "exit_cue": "",
            "line_hint": "",
        }
        if landmarks:
            ev.update({
                "map": landmarks.get("map", ""),
                "approach": landmarks.get("approach", ""),
                "brake_cue": landmarks.get("brake_cue", ""),
                "apex_cue": landmarks.get("apex_cue", ""),
                "exit_cue": landmarks.get("exit_cue", ""),
                "line_hint": landmarks.get("line_hint", landmarks.get("approach", "")),
            })
        if line_cfg:
            ev["line_hint"] = ev["line_hint"] or line_cfg.get("line_hint", "")
            inputs = line_cfg.get("inputs", {})
            ev["input_throttle"] = inputs.get("throttle", "patience")
            ev["input_brake"] = inputs.get("brake", "trail")
            ev["input_steer"] = inputs.get("steer", "progressive")
        return ev

    def investigate(self, summary, reference, frame=None, corner="",
                    landmarks=None, line_cfg=None, yaw_gate=None):
        """Return the highest-confidence root cause, or None."""
        if not summary or not summary.get("phases"):
            return None

        if yaw_gate is not None and getattr(yaw_gate, "gate", "") == "LOSS_OF_CONTROL":
            hit = self._check_loss_of_control(
                summary, reference, corner, landmarks, line_cfg,
            )
            if hit is not None:
                return hit

        candidates = []
        for fn in (
            self._check_throttle_under_lateral,
            self._check_steer_fight,
            self._check_exit_throttle_under_load,
            self._check_scrubbed_min_speed,
            self._check_entry_overspeed,
        ):
            hit = fn(summary, reference, corner, landmarks, line_cfg)
            if hit is not None:
                candidates.append(hit)

        if frame is not None:
            hit = self._check_instant_overspeed(frame, reference, corner, landmarks, line_cfg)
            if hit is not None:
                candidates.append(hit)

        if not candidates:
            return None
        candidates.sort(key=lambda c: c.confidence, reverse=True)
        return candidates[0]

    def investigate_offline(self, summary, reference, corner="", landmarks=None, yaw_gate=None):
        """Replay diagnosis without a live frame (archived laps)."""
        return self.investigate(
            summary, reference, frame=None, corner=corner,
            landmarks=landmarks, line_cfg=None, yaw_gate=yaw_gate,
        )

    def _finish(self, root_id, template_key, phase, ev, confidence):
        ev["root_cause_id"] = root_id
        ev["root_cause_label"] = self.ROOT_LABELS.get(root_id, root_id)
        return InvestigationResult(template_key, phase, ev, root_id, confidence)

    def _check_exit_throttle_under_load(self, summary, reference, corner, landmarks, line_cfg):
        exit_p = self._phase(summary, "exit")
        ref_exit = self._ref_phase(reference, "exit")
        if exit_p.get("samples", 0) < 3:
            return None

        max_thr = exit_p.get("max_throttle", 0.0)
        peak_ay = exit_p.get("peak_ay_g", 0.0)
        min_spd = exit_p.get("min_speed_kmh", 0.0)
        ref_thr = ref_exit.get("max_throttle", 0.0)
        ref_min = ref_exit.get("min_speed_kmh", min_spd)
        ref_ay = ref_exit.get("peak_ay_g", 0.0)

        thr_thresh = self._t("ROOT_EXIT_THR", 0.65)
        ay_thresh = self._t("ROOT_EXIT_AY", 0.75)
        if max_thr < thr_thresh or peak_ay < ay_thresh:
            return None
        if peak_ay >= 1.15:
            return None
        if min_spd > 150.0 and peak_ay > 0.5:
            return None
        if ref_exit and max_thr <= ref_thr + 0.15 and min_spd >= ref_min - 2.0:
            return None

        ev = self._base_evidence(corner, "exit", landmarks, line_cfg)
        ev["peak_ay_g"] = "%.2f" % peak_ay
        ev["max_throttle_pct"] = int(round(max_thr * 100.0))
        ev["min_speed_kmh"] = int(round(min_spd))
        ev["ref_min_speed_kmh"] = int(round(ref_min)) if ref_min else int(round(min_spd))
        ev["evidence_point"] = (
            "EXIT telemetry: %.0f%% throttle with %.2fG lateral load at %d km/h "
            "(your reference: %.0f%% throttle, min %d km/h)."
            % (max_thr * 100.0, peak_ay, min_spd, ref_thr * 100.0, ref_min)
        )
        ev["mechanism"] = (
            "Applying power while the tyre is still cornering shifts load off the front "
            "and overloads the rear — grip drops before the steering unwinds."
        )
        ev["fix_action"] = (
            "%s Wait until the wheel is straight and speed is rising — "
            "your clean lap opens throttle after %d km/h, not at %d km/h."
            % (ev.get("exit_cue") or "Unwind steering first.", ref_min, min_spd)
        )
        ev["expected_outcome"] = "Rear stays planted; exit matches your %.0f km/h reference." % ref_min
        conf = 0.75 + min(0.2, (max_thr - ref_thr) * 0.3 + (peak_ay - ref_ay) * 0.1)
        return self._finish("exit_throttle_under_load", "root_exit_throttle", "exit", ev, conf)

    def _check_throttle_under_lateral(self, summary, reference, corner, landmarks, line_cfg):
        """Mid-corner throttle overlap (e.g. Casino powering while turning)."""
        for phase_name in ("mid", "exit", "entry"):
            phase = self._phase(summary, phase_name)
            if phase.get("samples", 0) < 3:
                continue
            max_thr = phase.get("max_throttle", 0.0)
            peak_ay = phase.get("peak_ay_g", 0.0)
            if max_thr < 0.5 or peak_ay < 1.2:
                continue
            ref = self._ref_phase(reference, phase_name)
            if ref and max_thr <= ref.get("max_throttle", 0.0) + 0.1:
                continue

            ev = self._base_evidence(corner, phase_name, landmarks, line_cfg)
            ev["peak_ay_g"] = "%.2f" % peak_ay
            ev["max_throttle_pct"] = int(round(max_thr * 100.0))
            ev["phase_upper"] = phase_name.upper()
            ev["evidence_point"] = (
                "%s: %.0f%% throttle while peak lateral load was %.2fG — "
                "inputs overlapped instead of separating brake, turn, then power."
                % (phase_name.upper(), max_thr * 100.0, peak_ay)
            )
            ev["mechanism"] = (
                "The tyre cannot accelerate and corner at peak lateral force simultaneously; "
                "overlap forces a correction or a spin on the next phase."
            )
            ev["fix_action"] = (
                "%s Separate phases: finish braking, turn in, then throttle only as G falls."
                % (ev.get("apex_cue") or "Trail off brake before adding power.")
            )
            ev["expected_outcome"] = "One clean rotation — no mid-corner power fighting the front."
            return self._finish(
                "throttle_under_lateral", "root_throttle_overlap", phase_name, ev, 0.8,
            )
        return None

    def _check_steer_fight(self, summary, reference, corner, landmarks, line_cfg):
        best_phase = None
        best_corr = 0
        ref_corr = 0
        for phase_name in ("entry", "mid", "exit"):
            phase = self._phase(summary, phase_name)
            corr = phase.get("steer_corrections", 0)
            ref = self._ref_phase(reference, phase_name)
            ref_c = ref.get("steer_corrections", 0) if ref else 0
            if corr >= 3 and corr > ref_c + 1:
                if corr > best_corr:
                    best_corr = corr
                    ref_corr = ref_c
                    best_phase = phase_name

        if best_phase is None:
            return None

        phase = self._phase(summary, best_phase)
        ev = self._base_evidence(corner, best_phase, landmarks, line_cfg)
        ev["corrections"] = best_corr
        ev["ref_corrections"] = ref_corr
        ev["min_speed_kmh"] = int(round(phase.get("min_speed_kmh", 0.0)))
        ev["evidence_point"] = (
            "%s: %d steering direction changes (your reference: %d) — "
            "the car is off your arc and you are correcting mid-corner."
            % (best_phase.upper(), best_corr, ref_corr)
        )
        ev["mechanism"] = (
            "Each correction spends grip on steering instead of speed; "
            "usually caused by wrong entry position or carrying too much speed in."
        )
        ev["fix_action"] = (
            "Fix entry first — %s One steering input through the apex."
            % (ev.get("line_hint") or ev.get("approach") or "widen or tighten approach to match your reference.")
        )
        ev["expected_outcome"] = "Corrections drop to %d or fewer like your reference lap." % max(ref_corr, 1)
        conf = 0.72 + min(0.2, best_corr * 0.03)
        return self._finish("steer_fight", "root_steer_fight", best_phase, ev, conf)

    def _check_scrubbed_min_speed(self, summary, reference, corner, landmarks, line_cfg):
        exit_p = self._phase(summary, "exit")
        ref_exit = self._ref_phase(reference, "exit")
        if exit_p.get("samples", 0) < 3 or not ref_exit:
            return None

        min_spd = exit_p.get("min_speed_kmh", 0.0)
        ref_min = ref_exit.get("min_speed_kmh", min_spd)
        gap = ref_min - min_spd
        if gap < self._t("ROOT_SCRUB_GAP_KMH", 8.0):
            return None

        ev = self._base_evidence(corner, "exit", landmarks, line_cfg)
        ev["min_speed_kmh"] = int(round(min_spd))
        ev["ref_min_speed_kmh"] = int(round(ref_min))
        ev["speed_gap_kmh"] = int(round(gap))
        ev["evidence_point"] = (
            "Minimum speed %d km/h vs your reference %d km/h (%.0f km/h scrubbed) — "
            "you lost momentum mid-corner before the exit."
            % (min_spd, ref_min, gap)
        )
        ev["mechanism"] = (
            "Scrubbing usually means braking too late (overspeed then panic brake) "
            "or turning in too early and binding the front."
        )
        ev["fix_action"] = (
            "%s Brake earlier to arrive slower, or turn in later for a wider arc — "
            "target %d km/h minimum like your best lap."
            % (ev.get("brake_cue") or "Adjust entry marker.", ref_min)
        )
        ev["expected_outcome"] = "Min speed recovers to ~%d km/h without extra steering." % ref_min
        return self._finish("scrubbed_min_speed", "root_scrub_speed", "exit", ev, 0.7 + min(0.15, gap / 40.0))

    def _check_entry_overspeed(self, summary, reference, corner, landmarks, line_cfg):
        exit_p = self._phase(summary, "exit")
        ref_exit = self._ref_phase(reference, "exit")
        if exit_p.get("samples", 0) < 3:
            return None

        mean_brk = exit_p.get("mean_brake", 0.0)
        peak_ay = exit_p.get("peak_ay_g", 0.0)
        ref_brk = ref_exit.get("mean_brake", mean_brk) if ref_exit else mean_brk

        if mean_brk < ref_brk + 0.08 and peak_ay < 1.0:
            return None
        if mean_brk < 0.12:
            return None

        ev = self._base_evidence(corner, "entry", landmarks, line_cfg)
        ev["mean_brake"] = "%.2f" % mean_brk
        ev["peak_ay_g"] = "%.2f" % peak_ay
        ev["evidence_point"] = (
            "Heavy braking mid-corner (avg %.0f%% brake, %.2fG lateral) — "
            "you arrived faster than your reference and had to scrub speed on the arc."
            % (mean_brk * 100.0, peak_ay)
        )
        ev["mechanism"] = (
            "Overspeed on entry forces a panic brake or steering bind mid-corner; "
            "the time loss appears here even though the mistake was at the brake marker."
        )
        ev["fix_action"] = (
            "%s Brake earlier or harder at the same marker — "
            "your reference carries less mid-corner brake."
            % (ev.get("brake_cue") or "Move brake point earlier.")
        )
        ev["expected_outcome"] = "Mid-corner brake near zero; car rotates at the apex cue."
        return self._finish("entry_overspeed", "root_entry_overspeed", "entry", ev, 0.78)

    def _check_instant_overspeed(self, frame, reference, corner, landmarks, line_cfg):
        if frame is None:
            return None
        ref_exit = self._ref_phase(reference, "exit")
        ref_spd = ref_exit.get("min_speed_kmh", 0.0)
        if ref_spd < 25.0:
            return None
        tol = self._t("INPUT_SPEED_TOL_KMH", 5.0)
        delta = frame.speed_kmh - ref_spd
        if delta <= tol:
            return None

        ev = self._base_evidence(corner, "entry", landmarks, line_cfg)
        ev["speed_delta_kmh"] = int(round(delta))
        ev["ref_speed_kmh"] = int(round(ref_spd))
        ev["evidence_point"] = (
            "Arrived %d km/h faster than your reference (%d km/h) at this point."
            % (delta, int(ref_spd))
        )
        ev["mechanism"] = (
            "Extra entry speed forces a tighter line or a mid-corner lift — "
            "both cost more time than braking slightly earlier."
        )
        ev["fix_action"] = (
            "%s Aim for %d km/h at turn-in."
            % (ev.get("brake_cue") or "Brake earlier.", int(ref_spd))
        )
        ev["expected_outcome"] = "Car rotates cleanly at the apex without mid-corner brake."
        return self._finish("entry_overspeed", "root_entry_overspeed", "entry", ev, 0.7)

    def _check_loss_of_control(self, summary, reference, corner, landmarks, line_cfg):
        exit_p = self._phase(summary, "exit")
        if exit_p.get("samples", 0) < 2:
            return None

        peak_beta = exit_p.get("peak_beta_deg", 0.0)
        max_thr = exit_p.get("max_throttle", 0.0)
        peak_ay = exit_p.get("peak_ay_g", 0.0)
        min_spd = exit_p.get("min_speed_kmh", 0.0)

        ev = self._base_evidence(corner, "exit", landmarks, line_cfg)
        ev["peak_beta_deg"] = int(round(peak_beta))
        ev["min_speed_kmh"] = int(round(min_spd))

        if max_thr > 0.5 and peak_ay > 0.6:
            ev["evidence_point"] = (
                "Loss of control after %.0f%% throttle at %d km/h with %.2fG lateral — "
                "rear grip exceeded before the corner finished."
                % (max_thr * 100.0, min_spd, peak_ay)
            )
            ev["mechanism"] = (
                "This is a driver-input limit, not setup: power was applied while "
                "the tyre was still loaded laterally."
            )
            ev["fix_action"] = (
                "%s Full throttle only when steering is straight and G is falling."
                % (ev.get("exit_cue") or "Wait for the exit.")
            )
            root = "loss_of_control_exit"
        else:
            ev["evidence_point"] = (
                "Yaw spike at %d km/h (beta peak %d°) — inputs exceeded the grip envelope."
                % (min_spd, int(peak_beta))
            )
            ev["mechanism"] = "Sudden steering or brake changes overloaded the tyre."
            ev["fix_action"] = "Ease inputs — one smooth steering trace through the corner."
            root = "loss_of_control_exit"

        ev["expected_outcome"] = "Corner completes without counter-steer or spin."
        return self._finish(root, "root_loss_of_control", "exit", ev, 0.85)
