# ac_app/lib/line_strategy.py
# Context-aware racing lines: compromise chains, grip patches, car class — not geometric ideal only.

import json
import os

try:
    from line_defaults import LineDefaults
except ImportError:
    from .line_defaults import LineDefaults


class LineStrategyResult(object):
    __slots__ = ("template_key", "phase", "confidence", "evidence", "input_focus", "issue")

    def __init__(self, template_key, phase="entry", confidence=0.7, evidence=None, input_focus=None):
        self.template_key = template_key
        self.issue = template_key
        self.phase = phase
        self.confidence = confidence
        self.evidence = evidence or {}
        self.input_focus = input_focus or {}


class LineStrategyEngine(object):
    """
    Evaluate line vs *context*:
    - corner profile (late apex, compromise, tight rubber, maintenance)
    - compound chains (sacrifice corner A for corner B exit)
    - car downforce class (formula wide/min-speed vs GT V-line)
    - observable inputs only: brake, throttle, steer proxies
    """

    PROFILES_WIDE_OK = frozenset((
        "geometric", "late_apex", "traditional", "wide_exit",
    ))
    PROFILES_NARROW_OK = frozenset((
        "tight_rubber", "compromise_setup", "maintenance", "early_apex",
    ))

    def __init__(self, thresholds=None, car_profile=None, techniques=None):
        self.thresholds = thresholds or {}
        self.car_profile = car_profile or {}
        self.techniques = techniques or {}

    @classmethod
    def load_techniques(cls, path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (IOError, ValueError):
            return {}

    @classmethod
    def default_techniques_path(cls):
        return os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config", "driving_techniques.json",
        )

    def _t(self, key, default):
        return float(self.thresholds.get(key, default))

    @classmethod
    def load_car_profile(cls, path, car_id):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data.get(car_id) or data.get("default", {})
        except (IOError, ValueError):
            return {}

    @classmethod
    def default_car_profile_path(cls):
        return os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config", "car_line_profiles.json",
        )

    def _line_cfg(self, corner_cfg):
        if not corner_cfg:
            return {}
        return corner_cfg.get("line", corner_cfg.get("landmarks", {}))

    def _width_bias(self, line_cfg):
        return line_cfg.get("width_bias", "neutral")

    def _profile(self, line_cfg):
        return line_cfg.get("profile", "geometric")

    def _chain_context(self, line_cfg, chain_deltas):
        chain_id = line_cfg.get("chain")
        if not chain_id or not chain_deltas:
            return None
        corners = chain_deltas.get(chain_id, {})
        if not corners:
            return None
        role = line_cfg.get("chain_role", "")
        payoff = line_cfg.get("chain_payoff", "")
        setup_delta = corners.get(line_cfg.get("name", ""), 0.0)
        payoff_delta = corners.get(payoff, 0.0) if payoff else 0.0
        return {
            "chain_id": chain_id,
            "role": role,
            "setup_delta": setup_delta,
            "payoff_delta": payoff_delta,
            "corners": corners,
        }

    def _resolve_line_cfg(self, corner_cfg, spline_indexer=None):
        corner_cfg = corner_cfg or {}
        line_cfg = self._line_cfg(corner_cfg)
        if line_cfg.get("profile"):
            return dict(line_cfg)
        if spline_indexer is not None:
            inferred = spline_indexer.corner_line(
                corner_cfg.get("name", ""), self.car_profile,
            )
            return dict(inferred)
        return LineDefaults.infer(
            corner_cfg,
            corner_cfg.get("speed_class", "medium"),
            self.car_profile,
        )

    def _technique(self, key, fallback=""):
        tech = self.techniques.get(key, {})
        return tech.get("coaching", fallback)

    def _technique_for_input(self, brake_style, throttle_style, steer_style, issue_kind):
        downforce = self.car_profile.get("downforce_class", "medium")
        keys = self.car_profile.get("technique_keys", {})
        focus = {}
        brake_key = keys.get("brake", "")
        if issue_kind == "trail" or brake_style == "trail":
            if not brake_key:
                brake_key = (
                    "trail_brake_high_downforce" if downforce == "high"
                    else "trail_brake"
                )
            focus["brake"] = self._technique(brake_key)
        elif brake_style == "straight":
            focus["brake"] = self._technique("straight_line_brake")
        elif brake_style == "lift":
            focus["brake"] = self._technique(
                "maintenance_throttle",
                "Small lift — no heavy braking in this phase.",
            )

        throttle_key = keys.get("throttle", "")
        if throttle_style == "patience":
            focus["throttle"] = self._technique(
                throttle_key or "patience_throttle",
            )
        elif throttle_style == "maintenance":
            focus["throttle"] = self._technique("maintenance_throttle")
        elif throttle_style == "early":
            focus["throttle"] = self._technique(
                throttle_key or "early_throttle_vline",
            )

        steer_key = keys.get("steer", "")
        if steer_style == "minimal":
            focus["steer"] = self._technique(steer_key or "minimal_steer")
        elif steer_style == "progressive":
            focus["steer"] = self._technique(steer_key or "progressive_steer")
        return focus

    def _input_focus(self, line_cfg, issue_kind):
        inputs = line_cfg.get("inputs", {})
        focus = self._technique_for_input(
            inputs.get("brake", ""),
            inputs.get("throttle", ""),
            inputs.get("steer", ""),
            issue_kind,
        )
        if issue_kind in ("line_fight", "compromise_needed") and "brake" not in focus:
            downforce = self.car_profile.get("downforce_class", "medium")
            key = "trail_brake_high_downforce" if downforce == "high" else "trail_brake"
            focus["brake"] = self._technique(key)
        return focus

    def analyze(self, corner, summary, reference, corner_cfg=None,
                chain_deltas=None, spline_indexer=None):
        if not summary or not summary.get("phases"):
            return None
        corner_cfg = corner_cfg or {}
        line_cfg = self._resolve_line_cfg(corner_cfg, spline_indexer)
        if "line_hint" in corner_cfg.get("landmarks", {}) and not line_cfg.get("line_hint"):
            line_cfg["line_hint"] = corner_cfg["landmarks"]["line_hint"]
        line_cfg = dict(line_cfg)
        line_cfg["name"] = corner_cfg.get("name", corner)

        if spline_indexer is not None and not line_cfg.get("chain"):
            for chain in spline_indexer.line_chains():
                corners = chain.get("corners", [])
                if corner in corners:
                    line_cfg["chain"] = chain.get("id", "")
                    if not line_cfg.get("chain_role"):
                        line_cfg["chain_role"] = spline_indexer.chain_role_for(
                            corner, line_cfg["chain"],
                        )
                    if not line_cfg.get("chain_payoff") and corners:
                        line_cfg["chain_payoff"] = corners[-1]
                    break

        phases = summary["phases"]
        ref_phases = reference.get("phases", {}) if reference else {}
        entry = phases.get("entry", {})
        mid = phases.get("mid", {})
        exit_p = phases.get("exit", {})
        ref_entry = ref_phases.get("entry", {})
        ref_mid = ref_phases.get("mid", {})
        ref_exit = ref_phases.get("exit", {})

        entry_corr = entry.get("steer_corrections", 0)
        mid_corr = mid.get("steer_corrections", 0)
        entry_steer = entry.get("mean_steer_abs", 0.0)
        ref_entry_steer = ref_entry.get("mean_steer_abs", entry_steer)
        mid_min = mid.get("min_speed_kmh", 0.0)
        ref_mid_min = ref_mid.get("min_speed_kmh", mid_min)
        profile = self._profile(line_cfg)
        width_bias = self._width_bias(line_cfg)
        chain_ctx = self._chain_context(line_cfg, chain_deltas or {})

        surface = summary.get("surface", {})
        if surface.get("kerb_grip_loss", 0) >= 1 or surface.get("painted_kerb_slip", 0) >= 1:
            width_bias = "narrow"

        evidence = {
            "profile": profile,
            "width_bias": width_bias,
            "corrections": mid_corr,
            "min_speed_kmh": int(round(mid_min)),
            "ref_min_speed_kmh": int(round(ref_mid_min)) if ref_mid_min else 0,
            "line_hint": line_cfg.get("line_hint", line_cfg.get("approach", "")),
            "compromise_note": line_cfg.get("compromise_note", ""),
            "chain_role": line_cfg.get("chain_role", ""),
            "grip_note": line_cfg.get("grip_note", ""),
        }

        if mid_corr >= self._t("LINE_FIGHT_CORRECTIONS", 3):
            return LineStrategyResult(
                "line_fight", "mid", 0.9, evidence,
                self._input_focus(line_cfg, "line_fight"),
            )

        if chain_ctx and line_cfg.get("chain_role") == "setup":
            if (
                chain_ctx.get("payoff_delta", 99) < chain_ctx.get("setup_delta", 0)
                and mid_corr <= 2
            ):
                return None
            if mid_min < ref_mid_min - self._t("COMPROMISE_SPEED_KMH", 3.0) and mid_corr >= 2:
                ev = dict(evidence)
                ev["payoff_corner"] = line_cfg.get("chain_payoff", "")
                return LineStrategyResult(
                    "line_compromise", "entry", 0.8, ev,
                    self._input_focus(line_cfg, "compromise_needed"),
                )

        if profile == "tight_rubber" or width_bias == "narrow":
            if (
                ref_entry_steer > 0.02
                and entry_steer > ref_entry_steer + self._t("WIDE_STEER_DELTA", 0.04)
                and mid_min < ref_mid_min - self._t("TIGHT_LINE_SPEED_KMH", 3.0)
            ):
                return LineStrategyResult(
                    "line_too_wide", "entry", 0.82, evidence,
                    self._input_focus(line_cfg, "too_wide"),
                )
            if mid_corr >= 2 and profile == "tight_rubber":
                return LineStrategyResult(
                    "line_fight", "mid", 0.75, evidence,
                    self._input_focus(line_cfg, "line_fight"),
                )
            return None

        if width_bias == "wide" and profile in self.PROFILES_WIDE_OK:
            if (
                entry_corr >= self._t("NARROW_APPROACH_CORRECTIONS", 2)
                and entry_steer > ref_entry_steer + self._t("NARROW_STEER_DELTA", 0.03)
                and ref_mid_min > 0
                and mid_min < ref_mid_min - self._t("NARROW_MIN_SPEED_KMH", 4.0)
            ):
                return LineStrategyResult(
                    "line_wide_needed", "entry", 0.78, evidence,
                    self._input_focus(line_cfg, "narrow"),
                )

        if profile in ("late_apex", "geometric", "traditional", "wide_exit", "v_line"):
            ref_exit_throttle = ref_exit.get("max_throttle", 1.0)
            exit_throttle = exit_p.get("max_throttle")
            if (
                ref_mid_min > 0
                and mid_min < ref_mid_min - self._t("LATE_APEX_SPEED_KMH", 5.0)
                and exit_p.get("samples", 0) >= 2
                and exit_throttle is not None
                and exit_throttle < ref_exit_throttle - 0.12
            ):
                return LineStrategyResult(
                    "line_late_apex", "mid", 0.78, evidence,
                    self._input_focus(line_cfg, "late_apex"),
                )

        if profile == "early_apex" or line_cfg.get("chain_role") == "payoff":
            if (
                ref_mid_min > 0
                and mid_min < ref_mid_min - self._t("EARLY_APEX_SPEED_KMH", 4.0)
                and entry_corr >= 2
            ):
                ev = dict(evidence)
                ev["next_corner"] = line_cfg.get("chain_next", "")
                return LineStrategyResult(
                    "line_early_apex", "entry", 0.75, ev,
                    self._input_focus(line_cfg, "early_apex"),
                )

        if line_cfg.get("inputs", {}).get("brake") == "trail":
            entry_brake = entry.get("mean_brake", 0.0)
            if entry_brake < 0.08 and entry_corr >= 1 and mid_corr >= 1:
                return LineStrategyResult(
                    "input_trail_brake", "entry", 0.6, evidence,
                    self._input_focus(line_cfg, "trail"),
                )

        return None

    def chain_summary(self, chain_id, chain_meta, corner_deltas, spline_indexer):
        if not chain_meta or not corner_deltas:
            return None
        corners = chain_meta.get("corners", [])
        items = []
        total = 0.0
        for name in corners:
            d = corner_deltas.get(name, 0.0)
            total += d
            display = name
            if spline_indexer is not None:
                display = spline_indexer.corner_display_name(name)
            items.append((display, d))
        if not items:
            return None
        goal = chain_meta.get("goal", "Maximize chain exit speed")
        worst = max(items, key=lambda x: x[1])
        return {
            "chain_id": chain_id,
            "goal": goal,
            "total_delta_s": "%.2f" % total,
            "worst_corner": worst[0],
            "worst_delta_s": "%.2f" % worst[1],
            "action": "Treat %s as one complex — sacrifice early corners if %s gains time." % (
                chain_id.replace("_", " "), worst[0],
            ),
        }
