# ac_app/lib/line_analyzer.py
# Back-compat wrapper — delegates to LineStrategyEngine.

try:
    from line_strategy import LineStrategyEngine, LineStrategyResult
except ImportError:
    from .line_strategy import LineStrategyEngine, LineStrategyResult


LineIssue = LineStrategyResult


class LineAnalyzer(object):
    """Detect line/positioning issues with context-aware strategy."""

    def __init__(self, thresholds=None, car_profile=None, techniques=None):
        self._engine = LineStrategyEngine(thresholds, car_profile, techniques)

    @property
    def issue(self):
        return getattr(self._last, "template_key", None)

    def analyze(self, corner, summary, reference, landmarks=None,
                corner_cfg=None, chain_deltas=None, spline_indexer=None):
        cfg = corner_cfg
        if cfg is None and landmarks:
            cfg = {"landmarks": landmarks, "name": corner}
        result = self._engine.analyze(
            corner, summary, reference, cfg, chain_deltas, spline_indexer,
        )
        self._last = result
        return result
