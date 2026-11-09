"""Evidence-grounded telemetry coaching agent."""

import os
import sys

# Sibling modules use flat imports (they also run as scripts), so the package
# dirs must be importable before the relative imports below.
_COACH_DIR = os.path.dirname(os.path.abspath(__file__))
for _path in (os.path.dirname(_COACH_DIR), _COACH_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from .evidence_pack import build_evidence_pack, collect_evidence
from .incident_analyzer import analyze_lap_incidents, analyze_session_incidents
from .coach_service import ask_coach

__all__ = [
    "build_evidence_pack",
    "collect_evidence",
    "analyze_lap_incidents",
    "analyze_session_incidents",
    "ask_coach",
]
