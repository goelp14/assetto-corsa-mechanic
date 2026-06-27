# ac_app/lib/line_defaults.py
# Generic line profile when track JSON has no per-corner line block.


class LineDefaults(object):
    """Infer line strategy from speed class + car aero — any track."""

    @staticmethod
    def infer(corner_cfg=None, speed_class="medium", car_profile=None, next_corner=None):
        car_profile = car_profile or {}
        if corner_cfg and corner_cfg.get("line"):
            return dict(corner_cfg["line"])

        downforce = car_profile.get("downforce_class", "medium")
        line_bias = car_profile.get("line_bias", "traditional_wide")
        speed = speed_class or "medium"

        profile = "geometric"
        width_bias = "neutral"
        inputs = {"brake": "trail", "throttle": "patience", "steer": "progressive"}

        if downforce == "high" or line_bias == "traditional_wide":
            profile = "late_apex"
            width_bias = "wide" if speed != "high" else "neutral"
            inputs["throttle"] = "patience"
        elif line_bias == "v_line_exit":
            profile = "v_line" if speed == "low" else "geometric"
            width_bias = "neutral"
            inputs["throttle"] = "early" if speed == "low" else "patience"

        if speed == "high":
            profile = "maintenance"
            width_bias = "neutral"
            inputs = {"brake": "lift", "throttle": "maintenance", "steer": "minimal"}

        line = {
            "profile": profile,
            "width_bias": width_bias,
            "inputs": inputs,
        }
        if next_corner:
            line["chain_next"] = next_corner
        return line

    @staticmethod
    def infer_chains(corners, gap=0.05):
        """Build compound chains from spline proximity — works on any track JSON."""
        if not corners:
            return []
        ordered = sorted(corners, key=lambda c: c.get("spline_start", 0.0))
        chains = []
        group = [ordered[0]]
        for corner in ordered[1:]:
            prev = group[-1]
            prev_end = prev.get("spline_end", 0.0)
            start = corner.get("spline_start", 0.0)
            dist = start - prev_end
            if dist < 0.0:
                dist += 1.0
            if dist <= gap:
                group.append(corner)
            else:
                if len(group) >= 2:
                    chains.append(LineDefaults._chain_from_group(group))
                group = [corner]
        if len(group) >= 2:
            chains.append(LineDefaults._chain_from_group(group))
        return chains

    @staticmethod
    def _chain_from_group(group):
        names = [c.get("name", "") for c in group]
        cid = "auto_" + "_".join(n.replace(" ", "") for n in names[:2])
        roles = {}
        for i, name in enumerate(names):
            if i == 0:
                roles[name] = "setup"
            elif i == len(names) - 1:
                roles[name] = "payoff"
            else:
                roles[name] = "link"
        return {
            "id": cid,
            "corners": names,
            "goal": "Compound section — optimize exit of %s, not each apex alone." % names[-1],
            "roles": roles,
            "inferred": True,
        }
