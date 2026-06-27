# ac_app/lib/pace_opportunity.py
# Offline limit-pushing coaching — mirror of corner_investigator for opportunities.

from gg_envelope import GgEnvelope
from phase_pace import PhasePaceCoach


class PaceOpportunity(object):
    """One opportunity annotation for export / replay viewer."""

    __slots__ = ("subtype", "phase", "spline", "title", "what", "why", "action", "evidence")

    def __init__(self, subtype, phase, spline, title, what, why, action, evidence=None):
        self.subtype = subtype
        self.phase = phase
        self.spline = spline
        self.title = title
        self.what = what
        self.why = why
        self.action = action
        self.evidence = evidence or {}


class PaceOpportunityAnalyzer(object):
    """Find untapped pace on clean laps — grip, min-speed, micro-gains."""

    def __init__(self, thresholds=None):
        self.thresholds = thresholds or {}
        self._phase_pace = PhasePaceCoach(thresholds)
        self._gg = GgEnvelope()

    def observe_sample(self, speed_kmh, ay_g):
        self._gg.observe(speed_kmh, ay_g)

    def analyze_lap(self, lap_num, samples, sector_refs, spline_indexer,
                    potential_gap_s=0.0, line_cfg_map=None):
        """Return opportunity annotations for one lap."""
        annotations = []
        ann_id = 0
        corners_seen = set()

        for sample in samples:
            speed = sample.get("speed_kmh", 0.0)
            ay = sample.get("acc_g_lat", 0.0)
            self.observe_sample(speed, ay)

        for corner, ref in sector_refs.items():
            summary = self._build_summary(samples, corner)
            if not summary:
                continue
            corners_seen.add(corner)
            line_cfg = (line_cfg_map or {}).get(corner)
            display = corner
            if spline_indexer is not None:
                display = spline_indexer.corner_display_name(corner)

            micro = self._phase_pace.next_gain(
                summary, ref, display, potential_gap_s, line_cfg=line_cfg,
            )
            if micro and micro.get("kind") != "micro":
                ann_id += 1
                spline = self._corner_spline(samples, corner, spline_indexer)
                subtype = "micro_gain"
                if micro.get("kind") == "speed":
                    subtype = "pace_min_speed"
                elif micro.get("kind") == "grip":
                    subtype = "grip_left"
                annotations.append(self._to_annotation(
                    ann_id, lap_num, corner, display, spline, subtype, micro,
                ))

            ref_phases = ref.get("phases", {})
            for phase_name in ("entry", "mid", "exit"):
                phase = summary.get("phases", {}).get(phase_name, {})
                ref_p = ref_phases.get(phase_name, {})
                min_spd = phase.get("min_speed_kmh", 0)
                ref_spd = ref_p.get("min_speed_kmh", 0)
                gap = ref_spd - min_spd
                if ref_spd > 20 and gap >= 2.0:
                    ann_id += 1
                    spline = self._corner_spline(samples, corner, spline_indexer, phase_name)
                    annotations.append(PaceOpportunity(
                        subtype="pace_min_speed",
                        phase=phase_name,
                        spline=spline,
                        title="%s: min speed %d vs your %d km/h" % (
                            display, int(min_spd), int(ref_spd),
                        ),
                        what="CLEAN but %d km/h below your best min-speed at %s %s." % (
                            int(gap), display, phase_name.upper(),
                        ),
                        why="You are not on the limit yet — more commitment or line width.",
                        action="Match reference min-speed before adding throttle.",
                        evidence={
                            "min_speed_kmh": min_spd,
                            "ref_min_speed_kmh": ref_spd,
                            "gap_kmh": int(gap),
                        },
                    ))

        for sample in samples:
            speed = sample.get("speed_kmh", 0.0)
            ay = sample.get("acc_g_lat", 0.0)
            if speed < 40:
                continue
            left = self._gg.grip_left_pct(speed, ay)
            if left < 8:
                continue
            corner = sample.get("corner") or ""
            if not corner:
                continue
            ann_id += 1
            display = corner
            if spline_indexer is not None:
                display = spline_indexer.corner_display_name(corner)
            annotations.append(PaceOpportunity(
                subtype="grip_left",
                phase=sample.get("phase", "mid"),
                spline=sample.get("spline", 0.0),
                title="%d%% grip unused at %d km/h" % (left, int(speed)),
                what="Lateral G is below your personal envelope at this speed.",
                why="Tyres have headroom — you can commit more without exceeding your own limit.",
                action="Hold the reference line and carry more speed through %s." % display,
                evidence={
                    "grip_left_pct": left,
                    "speed_kmh": int(speed),
                    "ay_g": round(ay, 2),
                },
            ))
            break  # one grip annotation per lap max

        return annotations

    def detect_clean_lap_trap(self, lap_time_ms, potential_gap_s, avg_grip_usage,
                                min_speed_gaps):
        if potential_gap_s < 0.5:
            return None
        if avg_grip_usage >= 0.75 and len(min_speed_gaps) < 2:
            return None
        return {
            "message": "Clean but not fast — focus on opportunities, not corrections",
            "potential_gap_s": round(potential_gap_s, 3),
            "avg_grip_usage_pct": int(round(avg_grip_usage * 100)),
            "min_speed_corners": min_speed_gaps[:3],
        }

    def _build_summary(self, samples, corner):
        phases = {}
        for s in samples:
            if s.get("corner") != corner:
                continue
            phase = s.get("phase") or "exit"
            p = phases.setdefault(phase, {
                "samples": 0, "min_speed_kmh": 9999.0, "peak_ay_g": 0.0,
                "max_rear_slip": 0.0, "steer_corrections": 0,
            })
            p["samples"] += 1
            spd = s.get("speed_kmh", 0.0)
            if spd < p["min_speed_kmh"]:
                p["min_speed_kmh"] = spd
            ay = abs(s.get("acc_g_lat", 0.0))
            if ay > p["peak_ay_g"]:
                p["peak_ay_g"] = ay
        if not phases:
            return None
        for p in phases.values():
            if p["min_speed_kmh"] == 9999.0:
                p["min_speed_kmh"] = 0.0
        return {"phases": phases}

    def _corner_spline(self, samples, corner, spline_indexer, phase=None):
        for s in samples:
            if s.get("corner") == corner and (phase is None or s.get("phase") == phase):
                return s.get("spline", 0.0)
        if spline_indexer is not None:
            cfg = spline_indexer.corner_config(corner)
            if cfg:
                return (float(cfg.get("spline_start", 0)) + float(cfg.get("spline_end", 0))) * 0.5
        return 0.0

    def _to_annotation(self, ann_id, lap_num, corner, display, spline, subtype, micro):
        phase = micro.get("phase", "mid")
        detail = micro.get("detail", "") or ""
        if "km/h" in detail or "vs your" in detail.lower():
            action = detail
        elif micro.get("kind") == "pace_min_speed":
            action = "Carry more minimum speed on %s before picking up throttle." % phase
        else:
            action = "Compare your %s trace to your personal best at this corner." % phase
        return PaceOpportunity(
            subtype=subtype,
            phase=phase,
            spline=spline,
            title=micro.get("detail", "Opportunity at %s" % display)[:80],
            what=micro.get("detail", ""),
            why="Compared to your personal best phase at this corner.",
            action=action,
            evidence={
                "kind": micro.get("kind", ""),
                "gain_s": micro.get("gain_s", ""),
            },
        )

    def export_annotation(self, opp, lap_num, corner, corner_display, ann_id):
        return {
            "id": "opp_%03d" % ann_id,
            "lap": lap_num,
            "spline": round(opp.spline, 4),
            "corner": corner,
            "corner_display": corner_display,
            "phase": opp.phase,
            "category": "opportunity",
            "subtype": opp.subtype,
            "attribution": "driver",
            "title": opp.title,
            "what": opp.what,
            "why": opp.why,
            "action": opp.action,
            "evidence": opp.evidence,
            "source": "pace_opportunity",
        }

    def envelope_dict(self):
        return self._gg.to_dict()
