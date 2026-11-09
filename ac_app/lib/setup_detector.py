# ac_app/lib/setup_detector.py
# Python 3.3 compatible — stdlib only

try:
    from decision_engine import VERDICT_SETUP_FLAW, VERDICT_SETUP_STABILIZE
except ImportError:
    from .decision_engine import VERDICT_SETUP_FLAW, VERDICT_SETUP_STABILIZE


class SetupDelta(object):
    __slots__ = ("section", "delta", "reason", "tier", "old_value", "new_value")

    def __init__(self, section, delta, reason, tier="A", old_value=None, new_value=None):
        self.section = section
        self.delta = delta
        self.reason = reason
        self.tier = tier
        self.old_value = old_value
        self.new_value = new_value


class SetupFlawDetector(object):
    """Translate setup verdicts into lever-specific adjustments."""

    def __init__(self, setup_catalog, setup_memory=None, thresholds=None):
        self.catalog = setup_catalog
        self.memory = setup_memory
        self.thresholds = thresholds or {}

    def _thresh(self, key, default):
        return self.thresholds.get(key, default)

    def _performance_justified(self, decision, laps_persisting, context):
        ctx = context or {}
        ev = decision.evidence or {}
        min_delta = float(self._thresh("CORNER_DELTA_SETUP_S", 0.03))
        persist = int(self._thresh("SETUP_PERSIST_LAPS", 3))
        surface_persist = int(self._thresh("SURFACE_SETUP_PERSIST_LAPS", 2))
        stabilize_persist = int(self._thresh("SETUP_STABILIZE_PERSIST_LAPS", 2))
        memory_min = float(self._thresh("SETUP_MEMORY_MIN_WEIGHT", 0.15))

        if ctx.get("corner_delta_s", ev.get("corner_delta_s", 0.0)) >= min_delta:
            return True
        if ctx.get("setup_weight", 0.0) >= memory_min:
            return True
        if ev.get("performance_cost"):
            return True
        surface_symptoms = (
            "kerb_grip_loss", "painted_kerb_slip", "kerb_overload",
            "platform_hop", "bump_unsettled", "kerb_instability",
        )
        if decision.symptom in surface_symptoms:
            return laps_persisting >= surface_persist
        if decision.verdict == VERDICT_SETUP_STABILIZE:
            return laps_persisting >= stabilize_persist
        return laps_persisting >= persist

    def detect(self, decision, current_values, laps_persisting=0, context=None):
        if decision.verdict not in (VERDICT_SETUP_FLAW, VERDICT_SETUP_STABILIZE):
            return []

        if not self._performance_justified(decision, laps_persisting, context):
            return []

        symptom = decision.symptom or "mid_understeer"
        phase = decision.phase or "mid"
        surface_symptoms = (
            "kerb_grip_loss", "painted_kerb_slip", "kerb_overload",
            "platform_hop", "bump_unsettled", "kerb_instability",
        )
        tier_max = "A"
        if symptom in surface_symptoms:
            tier_max = "B"
        elif decision.verdict == VERDICT_SETUP_FLAW:
            persist = int(self._thresh("SETUP_PERSIST_LAPS", 3))
            if laps_persisting < persist:
                tier_max = "B" if laps_persisting >= 5 else "A"

        candidates = self.catalog.recommend(symptom, phase, tier_max=tier_max)
        if self.memory is not None:
            candidates = self.memory.rerank_candidates(candidates, symptom)
        constraints = getattr(self, "constraints", None)
        if constraints is not None:
            candidates = constraints.filter_candidates(candidates, symptom, context)

        deltas = []
        for cand in candidates:
            section = cand["section"]
            cur = current_values.get(section, 0)
            delta, new_val = self.catalog.validate_delta(section, cur, cand["delta"])
            if delta != 0:
                if self.memory is not None and not self.memory.approve_tweak(section, delta):
                    continue
                deltas.append(SetupDelta(
                    section, delta, cand.get("reason", ""),
                    tier=cand.get("tier", "A"),
                    old_value=cur, new_value=new_val,
                ))
                mirror = self.catalog.mirror_section(section)
                if mirror and self.catalog.lever(mirror) is not None:
                    m_cur = current_values.get(mirror, cur)
                    m_delta, m_new = self.catalog.validate_delta(mirror, m_cur, cand["delta"])
                    if m_delta != 0:
                        deltas.append(SetupDelta(
                            mirror, m_delta, cand.get("reason", ""),
                            tier=cand.get("tier", "A"),
                            old_value=m_cur, new_value=m_new,
                        ))
                break
            if self.catalog.is_at_limit(section, cur, cand["delta"]):
                for move in self.catalog.tradeoff_moves(section, cand["delta"], symptom):
                    parts = self.catalog.build_tradeoff_deltas(move, current_values)
                    if not parts:
                        continue
                    batch = []
                    for sec, d, nv, reason in parts:
                        if self.memory is not None and not self.memory.approve_tweak(sec, d):
                            batch = []
                            break
                        batch.append(SetupDelta(
                            sec, d, reason, tier=cand.get("tier", "A"),
                            old_value=current_values.get(sec, 0), new_value=nv,
                        ))
                    if batch:
                        return batch
        return deltas

    def advisory_only(self, decision):
        """Tier C/D recommendations without INI write."""
        symptom = decision.symptom or "mid_understeer"
        phase = decision.phase or "mid"
        return self.catalog.recommend(symptom, phase, tier_max="D")
