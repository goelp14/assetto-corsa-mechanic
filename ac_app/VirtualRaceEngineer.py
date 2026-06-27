# VirtualRaceEngineer.py — AC Python 3.3 entry point

import os
import json
import sys
import traceback

_APP_DIR = os.path.dirname(os.path.realpath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)


def _purge_stale_lib_modules():
    """CSP live reload re-runs this file but keeps old lib.* in sys.modules."""
    stale = []
    for key in sys.modules:
        if key == "lib" or key.startswith("lib."):
            stale.append(key)
    for key in stale:
        del sys.modules[key]


_purge_stale_lib_modules()


def _log_boot_error(label):
    try:
        log_dir = os.path.join(_APP_DIR, "data")
        if not os.path.isdir(log_dir):
            os.makedirs(log_dir)
        path = os.path.join(log_dir, "import_error.log")
        with open(path, "a") as fh:
            fh.write("\n=== %s ===\n" % label)
            traceback.print_exc(file=fh)
    except Exception:
        pass


try:
    import ac
    import acsys
except Exception:
    _log_boot_error("ac import")
    raise

try:
    from sim_info import info
    from lib.telemetry_ingest import TelemetryIngest
    from lib.spline_indexer import SplineIndexer
    from lib.volatility_buffer import VolatilityBuffer, PHASE_LEARNING, PHASE_BASELINE_READY, PHASE_TWEAKING
    from lib.session_state import SessionState, LAP_FLYING, LAP_OUT, LAP_IN
    from lib.dynamics_math import DynamicsMath
    from lib.balance_metrics import BalanceMetrics
    from lib.yaw_gates import YawGateEvaluator, GATE_LOSS_OF_CONTROL
    from lib.corner_phases import CornerPhaseSegmenter
    from lib.lap_time_analyzer import LapTimeAnalyzer
    from lib.baseline_store import BaselineStore
    from lib.decision_engine import DecisionEngine, VERDICT_DRIVER_ERROR, VERDICT_SETUP_FLAW, VERDICT_SETUP_STABILIZE, DecisionResult
    from lib.driver_classifier import DriverClassifier
    from lib.corner_investigator import CornerInvestigator
    from lib.setup_catalog import SetupCatalog
    from lib.setup_detector import SetupFlawDetector
    from lib.setup_writer import SetupWriter
    from lib.setup_memory import SetupMemory
    from lib.feedback_presenter import FeedbackPresenter
    from lib.feedback_manager import FeedbackManager
    from lib.voice_file_writer import VoiceFileWriter
    from lib.telemetry_archive import TelemetryArchive
    from lib.session_phase_store import SessionPhaseStore
    from lib.shift_analyzer import ShiftAnalyzer
    from lib.track_profile import TrackProfileStore
    from lib.setup_detector import SetupDelta
    from lib.setup_detection import build_detection_record
    from lib.ac_paths import resolve_track_setup_folder, resolve_car_setups_root, probe_setup_paths
    from lib.tyre_window import TyreWindowTracker
    from lib.corner_phase_metrics import CornerPhaseMetrics
    from lib.symptom_detector import SymptomDetector
    from lib.setup_constraints import SetupConstraints
    from lib.gg_envelope import GgEnvelope
    from lib.session_analyst import SessionAnalyst
    from lib.line_reference import LineReference
    from lib.line_analyzer import LineAnalyzer
    from lib.line_strategy import LineStrategyEngine
    from lib.phase_pace import PhasePaceCoach
    from lib.telemetry_context import build as build_telemetry_context
    from lib.grip_map import GripMapStore, format_grip_legend
    from lib.dashboard import EngineerDashboard
    from lib.hud_renderer import (
        build_snapshot, draw_hud, cue_style,
        format_delta, format_learn_line, format_learn_detail, format_phase_line,
        format_coach_hint, format_feedback_line, format_setup_hud_line, format_setup_pit_detail,
        temp_font_color, feedback_type_color,
        HUD_W, HUD_H, LBL_PIT_Y,
        LBL_LEARN, LBL_LEARN_DETAIL, LBL_SETUP, LBL_SPEED, LBL_SPEED_UNIT, LBL_DELTA,
        LBL_TYRE_COLS, LBL_TYRE_TAG_Y, LBL_TYRE_VAL_Y,
        LBL_STATUS, LBL_COACH, LBL_FEEDBACK, LBL_CUE1, LBL_CUE2,
    )
except Exception:
    _log_boot_error("VRE imports")
    raise

_app_window = 0
_ui_labels = {}
_ui_text_cache = {}
_hud_snapshot = None
_cue_alpha = 0.0
_last_in_pit = False
_HUD_W = HUD_W
_HUD_H = HUD_H

_ingest = None
_spline = None
_volatility = None
_session = None
_dynamics = None
_balance = None
_yaw_gates = None
_corner_phases = None
_lap_analyzer = None
_baselines = None
_decision = None
_driver_clf = None
_corner_investigator = None
_catalog = None
_setup_detector = None
_setup_writer = None
_setup_memory = None
_presenter = None
_feedback = None
_voice = None
_archive = None
_track_profiles = None
_track_profile = None
_tyre_tracker = None
_corner_metrics = None
_symptom_detector = None
_setup_constraints = None
_gg_envelope = None
_grip_map = None
_session_analyst = None
_line_ref = None
_line_analyzer = None
_phase_pace = None
_chain_deltas = {}
_active_tyre_symptoms = []
_lap_corner_summaries = {}
_dashboard = None
_driving_techniques = {}
_SURFACE_SYMPTOMS = frozenset((
    "kerb_grip_loss", "painted_kerb_slip", "kerb_overload",
    "platform_hop", "bump_unsettled",
))
_thresholds = {}
_car_cfg = {}
_track_folder = "generic"
_initialized = False
_last_track = ""
_lap_time_ms = 0
_last_setup_note = None
_pit_tweak_queue = []
_session_phase = None
_session_flying_laps = 0
_session_best_lap_ms = 0
_shift_analyzer = None
_shift_corner_counts = {}


def _config_path(name):
    return os.path.join(_APP_DIR, "config", name)


def _data_path(*parts):
    return os.path.join(_APP_DIR, "data", *parts)


def _load_json(path, default=None):
    try:
        with open(path, "r") as fh:
            return json.load(fh)
    except (IOError, ValueError):
        return default if default is not None else {}


_last_volatility_phase = PHASE_LEARNING


def _resolve_track_folder(track_name, track_cfg=None):
    car_id = _car_cfg.get("car_id", "rss_formula_hybrid_x_2026") if _car_cfg else None
    return resolve_track_setup_folder(track_name, track_cfg=track_cfg, car_id=car_id)


def _find_base_setup(track_folder):
    if _setup_writer is not None:
        return _setup_writer.find_base_ini(track_folder)
    folder = os.path.join(resolve_car_setups_root(), track_folder)
    if not os.path.isdir(folder):
        return None
    for fname in sorted(os.listdir(folder)):
        if fname.lower().endswith(".ini") and fname.lower() != "auto_tweak.ini":
            return os.path.join(folder, fname)
    return None


def _apply_remaining_bootstrap(frame, limit=None, force_immediate=False):
    if _track_profile is None:
        return 0
    applied = 0
    while _track_profile._bootstrap_index < len(_track_profile.bootstrap_hints):
        if limit is not None and applied >= limit:
            break
        hint = _track_profile.next_bootstrap_hint()
        if hint is None:
            break
        if _apply_bootstrap_hint(hint, frame, force_immediate=force_immediate):
            applied += 1
        else:
            break
    return applied


def _read_setup_values(ini_path):
    values = {}
    if not ini_path or not os.path.isfile(ini_path):
        return values
    section = None
    with open(ini_path, "r") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1]
            elif section and line.upper().startswith("VALUE="):
                try:
                    values[section] = float(line.split("=", 1)[1])
                except ValueError:
                    values[section] = line.split("=", 1)[1]
    return values


def _init_modules():
    global _ingest, _spline, _volatility, _session, _dynamics, _balance
    global _yaw_gates, _corner_phases, _lap_analyzer, _baselines, _decision
    global _driver_clf, _catalog, _setup_detector, _setup_writer, _setup_memory
    global _corner_investigator
    global _presenter, _feedback, _voice, _archive, _track_profiles, _tyre_tracker
    global _corner_metrics, _symptom_detector, _setup_constraints, _gg_envelope, _session_analyst
    global _line_ref, _line_analyzer, _phase_pace, _driving_techniques
    global _dashboard, _thresholds, _car_cfg, _session_phase, _shift_analyzer
    global _initialized

    if _initialized:
        return

    _thresholds = _load_json(_config_path("thresholds.json"), {})
    _car_cfg = _load_json(_config_path("car_rss_fh_x_2026.json"), {})

    _ingest = TelemetryIngest(info)
    _spline = SplineIndexer()
    _volatility = VolatilityBuffer(thresholds=_thresholds)
    _session = SessionState()
    _dynamics = DynamicsMath(car_config=_car_cfg)
    _balance = BalanceMetrics(car_config=_car_cfg, thresholds=_thresholds)
    _yaw_gates = YawGateEvaluator(_thresholds)
    _corner_phases = CornerPhaseSegmenter(spline_indexer=_spline)
    _lap_analyzer = LapTimeAnalyzer(
        num_buckets=_spline.num_buckets,
        track_length_m=5793,
        spline_indexer=_spline,
    )
    _baselines = BaselineStore(num_buckets=_spline.num_buckets, data_dir=_data_path("baselines"))
    _decision = DecisionEngine(_thresholds)
    _corner_investigator = CornerInvestigator(_thresholds)
    _driver_clf = DriverClassifier(_thresholds, investigator=_corner_investigator)
    _catalog = SetupCatalog(
        _config_path("car_rss_fh_x_2026.json"),
        _config_path("setup_symptom_map.json"),
    )
    _catalog.load_tradeoffs(_config_path("setup_tradeoffs.json"))
    _setup_memory = SetupMemory(data_dir=_data_path("setup_memory"), thresholds=_thresholds)
    _setup_detector = SetupFlawDetector(_catalog, _setup_memory, _thresholds)
    _setup_constraints = SetupConstraints(_config_path("setup_constraints.json"))
    _setup_detector.constraints = _setup_constraints
    _setup_writer = SetupWriter(_catalog)
    _presenter = FeedbackPresenter(_config_path("feedback_templates.json"))
    _voice = VoiceFileWriter(_data_path("engineer_voice.txt"))
    _feedback = FeedbackManager(
        voice_writer=_voice,
        ticker_duration_s=_thresholds.get("TICKER_DURATION", 5.0),
    )
    _archive = TelemetryArchive(
        sessions_dir=_data_path("sessions"),
        subsample_every=int(
            _thresholds.get(
                "ARCHIVE_EVERY_N",
                _thresholds.get("TELEMETRY_SUBSAMPLE_EVERY", 15),
            )
        ),
        max_lap_samples=int(_thresholds.get("TELEMETRY_MAX_LAP_SAMPLES", 1200)),
        async_writes=True,
    )
    _track_profiles = TrackProfileStore(_config_path("track_profiles.json"))
    _tyre_tracker = TyreWindowTracker(_config_path("tyre_windows.json"), _thresholds)
    _corner_metrics = CornerPhaseMetrics(_thresholds)
    _symptom_detector = SymptomDetector(_thresholds)
    _gg_envelope = GgEnvelope()
    _grip_map = GripMapStore(data_dir=_data_path("grip_map"), thresholds=_thresholds)
    _session_analyst = SessionAnalyst()
    _line_ref = LineReference(data_dir=_data_path("line_refs"))
    car_id = _car_cfg.get("car_id", "rss_formula_hybrid_x_2026")
    car_line = LineStrategyEngine.load_car_profile(
        _config_path("car_line_profiles.json"), car_id,
    )
    _driving_techniques = LineStrategyEngine.load_techniques(
        _config_path("driving_techniques.json"),
    )
    _line_analyzer = LineAnalyzer(_thresholds, car_line, _driving_techniques)
    _phase_pace = PhasePaceCoach(_thresholds)
    _dashboard = EngineerDashboard()
    _session_phase = SessionPhaseStore(data_dir=_data_path("session_phase"))
    _shift_analyzer = ShiftAnalyzer(thresholds=_thresholds, spline_indexer=_spline)

    _session.on_lap_complete(_on_lap_complete)
    _session.on_pit_entry(_on_pit_entry)
    _session.on_pit_exit(_on_pit_exit)
    _session.on_corner_exit(_on_corner_exit)

    _initialized = True


def _restore_last_setup_note():
    global _last_setup_note
    if _setup_memory is None or not _setup_memory.tweaks:
        _last_setup_note = None
        return
    rec = _setup_memory.tweaks[-1]
    section = rec.get("parameter", "")
    lever = _catalog.lever(section) if _catalog else None
    _last_setup_note = {
        "section": section,
        "section_display": lever.name if lever else section,
        "old_value": rec.get("old_value"),
        "new_value": rec.get("new_value"),
        "delta": rec.get("delta", 0),
        "reason": rec.get("symptom", ""),
        "why": "",
        "action": "Load Auto_Tweak.ini in the setup screen.",
        "source": "bootstrap" if rec.get("symptom") == "bootstrap" else "eval",
        "corner": rec.get("corner", ""),
    }


def _remember_setup_tweak(d0, source, why="", action="", corner=""):
    global _last_setup_note
    lever = _catalog.lever(d0.section) if _catalog else None
    _last_setup_note = {
        "section": d0.section,
        "section_display": lever.name if lever else d0.section,
        "old_value": d0.old_value,
        "new_value": d0.new_value,
        "delta": d0.delta,
        "reason": d0.reason or "",
        "why": why,
        "action": action or "Load Auto_Tweak.ini in the setup screen.",
        "source": source,
        "corner": corner,
    }


def _save_session_phase(track_name=None):
    track = track_name or _last_track
    if not track or _session_phase is None or _volatility is None:
        return
    _session_phase.save(
        track, _volatility.phase,
        _volatility.clean_laps, _volatility.total_laps,
    )


def _load_track(track_name):
    global _track_folder, _lap_analyzer, _track_profile, _volatility
    global _gg_envelope, _corner_metrics, _active_tyre_symptoms, _lap_corner_summaries
    global _session_flying_laps, _session_best_lap_ms, _shift_corner_counts
    global _pit_tweak_queue
    safe = track_name.replace(" ", "_").lower()
    path = _config_path(os.path.join("tracks", safe + ".json"))
    if not os.path.isfile(path):
        path = _config_path("tracks/monza.json")
    cfg = _load_json(path, {})
    _spline.load_config(cfg)
    _track_folder = _resolve_track_folder(track_name, cfg)
    _track_profile = _track_profiles.resolve(track_name)
    _track_profile.reset_bootstrap()
    _baselines.load(track_name)
    phase_state = _session_phase.load(
        track_name, baseline_sample_total=_baselines.sample_total(),
    )
    _volatility.phase = phase_state["phase"]
    _volatility.clean_laps = phase_state["clean_laps"]
    _volatility.total_laps = phase_state["total_laps"]
    _session.set_phase(_volatility.phase)
    _session_flying_laps = 0
    _session_best_lap_ms = 0
    _shift_corner_counts = {}
    if _shift_analyzer is not None:
        _shift_analyzer.spline_indexer = _spline
        _shift_analyzer.reset_lap()
    _lap_analyzer.track_length_m = cfg.get("length_m", 5793)
    _lap_analyzer.spline_indexer = _spline
    _corner_phases.spline_indexer = _spline
    _setup_memory.load(track_name)
    _restore_last_setup_note()
    if _setup_writer is not None:
        _setup_writer._active_setups_root = None
    if _archive is not None:
        car_id = _car_cfg.get("car_id", "rss_formula_hybrid_x_2026") if _car_cfg else None
        _archive.append_record({
            "record_type": "setup_path_probe",
            "track": track_name,
            "track_folder": _track_folder,
            "probe": probe_setup_paths(_track_folder, car_id=car_id),
            "base_ini": _find_base_setup(_track_folder) or "",
        })
    if _gg_envelope is not None:
        _gg_envelope.reset()
    if _grip_map is not None:
        _grip_map.load(track_name)
    if _corner_metrics is not None:
        _corner_metrics.reset_lap()
    _active_tyre_symptoms = []
    _lap_corner_summaries = {}
    _pit_tweak_queue = []
    if _line_ref is not None:
        _line_ref.load(track_name)


def _handle_shift_event(event):
    global _shift_corner_counts
    if event is None or _archive is None:
        return
    _archive.record_shift_event(event)
    if not _coaching_allowed() and not _setup_tweaks_allowed():
        return
    if event.is_coaching() and event.template_key:
        ev = _presenter.render(event.template_key, _shift_analyzer.coaching_evidence(event))
        _feedback.enqueue(ev)
        if event.corner and _shift_analyzer is not None:
            sym = _shift_analyzer.primary_corner_symptom(event.corner) or event.template_key
            key = "%s:%s" % (event.corner, sym)
            _shift_corner_counts[key] = _shift_corner_counts.get(key, 0) + 1
    elif (
        event.quality == "good"
        and event.template_key.startswith("shift_settling")
        and _coaching_allowed()
    ):
        n = int(_thresholds.get("SHIFT_PRAISE_EVERY_N", 5))
        if n > 1 and len(_shift_analyzer._lap_events) % n != 0:
            return
        ev = _presenter.render(event.template_key, _shift_analyzer.coaching_evidence(event))
        _feedback.enqueue(ev)


def _maybe_apply_shift_setup(symptom, phase, frame, corner):
    if _shift_analyzer is None or not _setup_tweaks_allowed():
        return False
    persist = int(_thresholds.get("SHIFT_SETUP_PERSIST", 2))
    key = "%s:%s" % (corner, symptom)
    if _shift_corner_counts.get(key, 0) < persist:
        return False
    base_ini = _find_base_setup(_track_folder)
    out_ini = _setup_writer.resolve_output_path(_track_folder)
    if base_ini and not os.path.isfile(out_ini):
        _setup_writer.clone_base(base_ini, out_ini)
    values = _read_setup_values(out_ini if os.path.isfile(out_ini) else base_ini)
    decision = DecisionResult(
        VERDICT_SETUP_STABILIZE, 0.1, 0.4, symptom, corner, phase,
        evidence={"performance_cost": True},
    )
    ctx = {"corner_delta_s": _lap_analyzer.corner_delta(corner) if _lap_analyzer else 0.0}
    deltas = _setup_detector.detect(
        decision, values, laps_persisting=persist, context=ctx,
    )
    if not deltas:
        return False
    return _apply_setup_deltas(
        deltas, frame, corner=corner, phase=phase, symptom=symptom,
    )


def _surface_technique_focus(symptom):
    key_map = {
        "kerb_grip_loss": "kerb_grip_loss",
        "painted_kerb_slip": "kerb_grip_loss",
        "kerb_overload": "kerb_overload",
        "platform_hop": "kerb_grip_loss",
        "bump_unsettled": "bump_platform",
    }
    tech = _driving_techniques.get(key_map.get(symptom, ""), {})
    focus = {}
    inp = tech.get("input", "")
    if inp and tech.get("coaching"):
        focus[inp] = tech["coaching"]
    return focus


def _build_chain_deltas():
    if _spline is None or _lap_analyzer is None:
        return {}
    out = {}
    for chain in _spline.line_chains():
        cid = chain.get("id", "")
        if not cid:
            continue
        corners = {}
        for name in chain.get("corners", []):
            corners[name] = _lap_analyzer.corner_delta(name)
        out[cid] = corners
    return out


def _merge_input_focus(evidence, input_focus):
    ev = dict(evidence)
    focus = input_focus or {}
    ev["input_brake"] = focus.get("brake", "")
    ev["input_throttle"] = focus.get("throttle", "")
    ev["input_steer"] = focus.get("steer", "")
    return ev


def _enrich_feedback_evidence(evidence, corner):
    ev = dict(evidence)
    ev["corner"] = corner or ev.get("corner", "")
    ev["corner_name"] = _spline.corner_display_name(ev["corner"])
    for key, value in _spline.corner_landmarks(ev["corner"]).items():
        ev.setdefault(key, value)
    for key in ("map", "approach", "brake_cue", "apex_cue", "exit_cue"):
        ev.setdefault(key, "")
    return ev


def _setup_context(corner, symptom, telemetry_ctx=None):
    speed_class = "medium"
    if _spline is not None and corner:
        speed_class = _spline.corner_speed_class(corner)
    ctx = {
        "tyre_axles": _setup_constraints.blocked_axles(_active_tyre_symptoms),
        "active_symptoms": list(_active_tyre_symptoms),
        "speed_class": speed_class,
    }
    if telemetry_ctx:
        ctx.update({
            "corner_delta_s": telemetry_ctx.get("corner_delta_s", 0.0),
            "setup_weight": telemetry_ctx.get("setup_weight", 0.0),
            "surface_severity": telemetry_ctx.get("surface_severity", 0.0),
            "performance_cost": telemetry_ctx.get("performance_cost", False),
            "surface": telemetry_ctx.get("surface", {}),
        })
    return ctx


def _symptom_from_balance(bal):
    if not bal.valid:
        return "mid_understeer"
    import math
    d = math.degrees(bal.delta_us)
    if d > 2.0:
        return "mid_understeer"
    if d < -2.0:
        return "exit_oversteer"
    if bal.ay_efficiency < 0.92:
        return "mid_understeer"
    return "mid_understeer"


def _metrics_snapshot(lap_time_ms, corner="", summary=None, balance=None,
                      corner_deltas=None):
    sym_m = 0.0
    corner_delta = 0.0
    if corner_deltas and corner:
        corner_delta = corner_deltas.get(corner, 0.0)
    elif _lap_analyzer is not None and corner:
        corner_delta = _lap_analyzer.corner_delta(corner)
    if summary:
        from lib.telemetry_context import symptom_metric
        sym_m = symptom_metric(summary, balance)
    elif balance is not None and balance.valid:
        import math
        sym_m = abs(math.degrees(balance.delta_us)) * 0.05
    return {
        "lap_time_ms": lap_time_ms,
        "corner_delta": corner_delta,
        "symptom_metric": sym_m,
    }


def _completed_lap_time_ms(frame):
    last_ms = getattr(info.graphics, "iLastTime", 0)
    if last_ms and last_ms > 1000:
        return int(last_ms)
    if hasattr(ac, "getCarState") and acsys is not None:
        return int(ac.getCarState(0, acsys.CS.LapTime))
    return int(frame.t * 1000)


def _pit_queue_count():
    return len(_pit_tweak_queue)


def _queue_pit_tweak(d0, frame, corner="", phase="", symptom="", source="eval",
                     notify=True, detection=None):
    global _pit_tweak_queue, _last_setup_note
    if d0 is None:
        return False
    if detection is None:
        detection = build_detection_record(
            None, corner,
            _spline.corner_display_name(corner) if _spline and corner else corner,
            phase, frame.spline, symptom, source=source, reason=d0.reason or "",
        )
    _pit_tweak_queue = [
        item for item in _pit_tweak_queue if item["delta"].section != d0.section
    ]
    _pit_tweak_queue.append({
        "delta": d0,
        "corner": corner,
        "phase": phase,
        "symptom": symptom,
        "source": source,
        "lap": frame.lap,
        "detection": detection,
    })
    lever = _catalog.lever(d0.section) if _catalog else None
    _last_setup_note = {
        "section": d0.section,
        "section_display": lever.name if lever else d0.section,
        "old_value": d0.old_value,
        "new_value": d0.new_value,
        "delta": d0.delta,
        "reason": d0.reason or symptom or "",
        "why": "Car balance cost detected — will try this in pits.",
        "action": "Auto_Tweak writes on pit entry — load it in setup.",
        "source": source,
        "corner": corner,
        "queued": True,
        "queue_count": len(_pit_tweak_queue),
    }
    if _archive is not None:
        queued = {
            "record_type": "setup_queued",
            "lap": frame.lap,
            "section": d0.section,
            "delta": d0.delta,
            "old_value": d0.old_value,
            "new_value": d0.new_value,
            "symptom": symptom,
            "corner": corner,
            "queue_size": len(_pit_tweak_queue),
            "reason": d0.reason or "",
        }
        queued.update(detection)
        _archive.append_record(queued)
    if notify and _presenter is not None:
        sign = "+" if d0.delta >= 0 else ""
        _feedback.enqueue(_presenter.render("setup_queued", {
            "section_name": _last_setup_note["section_display"],
            "delta_sign": sign,
            "delta_abs": abs(d0.delta),
            "queue_count": len(_pit_tweak_queue),
            "reason": d0.reason or symptom or "balance",
        }))
    return True


def _flush_pit_tweak_queue(frame):
    global _pit_tweak_queue
    if not _pit_tweak_queue or _setup_writer is None:
        return False
    queued = list(_pit_tweak_queue)
    deltas = [item["delta"] for item in queued]
    primary_item = queued[0]
    applied = _apply_setup_deltas(
        deltas, frame,
        corner=primary_item.get("corner", ""),
        phase=primary_item.get("phase", ""),
        symptom=primary_item.get("symptom", ""),
        notify=False,
        force_immediate=True,
        detection=primary_item.get("detection"),
        pit_entry=True,
        queued_lap=primary_item.get("lap"),
    )
    if applied:
        count = len(queued)
        names = ", ".join(item["delta"].section for item in queued[:3])
        _pit_tweak_queue = []
        if _last_setup_note is not None:
            _last_setup_note["queued"] = False
            _last_setup_note["action"] = "Auto_Tweak.ini updated — load it now."
            _last_setup_note["queue_count"] = 0
        if _presenter is not None and _feedback is not None:
            _feedback.enqueue(_presenter.render("pit_auto_apply", {
                "change_count": count,
                "sections": names,
            }))
    return applied


def _revert_setup_ini(rec):
    if _setup_writer is None or not rec:
        return False
    param = rec.get("parameter")
    old_val = rec.get("old_value")
    if not param or old_val is None:
        return False
    out_ini = _setup_writer.resolve_output_path(_track_folder)
    if not os.path.isfile(out_ini):
        return False
    d0 = SetupDelta(
        param, 0, "revert ineffective tweak",
        old_value=rec.get("new_value"), new_value=old_val,
    )
    _setup_writer.apply_deltas(out_ini, [d0], lap=rec.get("lap_applied", 0), reason="revert")
    if _archive is not None:
        _archive.append_record({
            "record_type": "setup_reverted",
            "parameter": param,
            "restored_value": old_val,
            "tweak_id": rec.get("tweak_id", ""),
        })
    return True


def _apply_setup_deltas(deltas, frame, corner="", phase="", symptom="", notify=True,
                        force_immediate=False, detection=None, pit_entry=False,
                        queued_lap=None, result=None, telem_ctx=None):
    if not deltas:
        return False
    source = "bootstrap" if symptom == "bootstrap" else (
        "tyre" if symptom and "tyre" in symptom else "eval"
    )
    if detection is None and (result is not None or corner or symptom):
        detection = build_detection_record(
            result, corner,
            _spline.corner_display_name(corner) if _spline and corner else corner,
            phase, frame.spline, symptom, telem_ctx=telem_ctx,
            source=source, reason=deltas[0].reason or "",
        )
    if not force_immediate and not frame.in_pit:
        for d0 in deltas:
            _queue_pit_tweak(
                d0, frame, corner=corner, phase=phase,
                symptom=symptom, source=source,
                notify=notify and d0 is deltas[0],
                detection=detection,
            )
        return True
    out_ini = _setup_writer.resolve_output_path(_track_folder)
    base_ini = _find_base_setup(_track_folder)
    if not os.path.isfile(out_ini):
        out_ini, setup_err = _setup_writer.ensure_auto_tweak(_track_folder)
        if setup_err and _archive is not None:
            _archive.append_record({
                "record_type": "setup_apply_failed",
                "lap": frame.lap,
                "section": deltas[0].section,
                "reason": setup_err,
                "track_folder": _track_folder,
                "base_ini": base_ini or "",
                "out_ini": out_ini or _setup_writer.resolve_output_path(_track_folder),
                "setups_root": _setup_writer._documents_setups_dir(),
            })
    if not os.path.isfile(out_ini):
        if _archive is not None:
            _archive.append_record({
                "record_type": "setup_apply_failed",
                "lap": frame.lap,
                "section": deltas[0].section,
                "reason": "no_output_ini",
                "track_folder": _track_folder,
                "base_ini": base_ini or "",
                "out_ini": out_ini or _setup_writer.resolve_output_path(_track_folder),
                "setups_root": _setup_writer._documents_setups_dir(),
            })
        return False
    _setup_writer.apply_deltas(
        out_ini, deltas, lap=frame.lap, reason=deltas[0].reason or symptom,
    )
    primary = deltas[0]
    if len(deltas) > 1:
        summary = ", ".join(
            "%s%+d" % (d.section, d.delta) for d in deltas
        )
        ev = _presenter.render("setup_tradeoff", {
            "section_name": primary.section,
            "reason": primary.reason,
            "change_summary": summary,
        })
        _remember_setup_tweak(
            primary, source=source,
            why=ev.why,
            action=ev.action,
            corner=corner,
        )
    else:
        ev = _presenter.from_setup_delta(primary, corner=corner)
        _remember_setup_tweak(
            primary, source=source,
            why=ev.why or primary.reason or "",
            action=ev.action,
            corner=corner,
        )
    if notify:
        _feedback.enqueue(ev)
    tweak_id = _setup_memory.record_pending(
        primary, frame.lap, corner=corner, phase=phase,
        symptom=symptom,
        before=_metrics_snapshot(_lap_time_ms, corner, summary=_lap_corner_summaries.get(corner)),
    )
    ctx = dict(detection or {})
    ctx.update({
        "lap": frame.lap,
        "pit_entry": bool(pit_entry or frame.in_pit),
        "queued_lap": queued_lap if queued_lap is not None else ctx.get("lap"),
        "source": source,
        "delta": primary.delta,
        "reason": primary.reason or symptom or ctx.get("detection_why", ""),
    })
    for d0 in deltas:
        _archive.record_setup_change(
            tweak_id if d0 is primary else "%s_%s" % (tweak_id, d0.section),
            d0.section, d0.old_value, d0.new_value,
            symptom=symptom, reason=d0.reason or ctx.get("reason", ""),
            **ctx
        )
    _archive.note_setup_tweak(len(deltas))
    _archive.append_record({
        "record_type": "setup_file_written",
        "lap": frame.lap,
        "path": out_ini,
        "sections": [d0.section for d0 in deltas],
    })
    return True


def _apply_setup_delta(d0, frame, corner="", phase="", symptom="", notify=True,
                       force_immediate=False, detection=None):
    return _apply_setup_deltas(
        [d0], frame, corner=corner, phase=phase,
        symptom=symptom, notify=notify, force_immediate=force_immediate,
        detection=detection,
    )


def _apply_bootstrap_hint(hint, frame, force_immediate=False):
    base_ini = _find_base_setup(_track_folder)
    out_ini = _setup_writer.resolve_output_path(_track_folder)
    values = _read_setup_values(
        out_ini if os.path.isfile(out_ini) else base_ini
    )
    section = hint["section"]
    cur = values.get(section, 0)
    delta, new_val = _catalog.validate_delta(section, cur, hint["delta"])
    if delta == 0:
        return False
    d0 = SetupDelta(
        section, delta, hint.get("reason", ""),
        tier="A", old_value=cur, new_value=new_val,
    )
    boot_detection = build_detection_record(
        None, "", _track_profile.display_name if _track_profile else "",
        "", frame.spline, "bootstrap", source="bootstrap",
        reason=hint.get("reason", ""),
    )
    if not _apply_setup_delta(
        d0, frame, symptom="bootstrap", notify=False,
        force_immediate=force_immediate, detection=boot_detection,
    ):
        return False
    sign = "+" if delta >= 0 else ""
    ev = _presenter.render("bootstrap_setup", {
        "track": _track_profile.display_name,
        "traits": _track_profile.traits_summary,
        "section_name": section,
        "delta_sign": sign,
        "delta_abs": abs(delta),
        "reason": hint.get("reason", ""),
    })
    _remember_setup_tweak(
        d0, source="bootstrap",
        why=ev.why,
        action=ev.action,
    )
    _feedback.enqueue(ev)
    return True


def _sync_tyre_compound():
    compound = getattr(info.graphics, "tyreCompound", "") or ""
    if compound:
        _tyre_tracker.set_compound(compound)


def _apply_tyre_diagnoses(diagnoses, frame):
    if not diagnoses or not _tyre_setup_allowed():
        return

    base_ini = _find_base_setup(_track_folder)
    out_ini = _setup_writer.resolve_output_path(_track_folder)
    values = _read_setup_values(
        out_ini if os.path.isfile(out_ini) else base_ini
    )

    for dx in diagnoses:
        candidates = _catalog.recommend(dx.symptom, "any", tier_max="C")
        if _setup_memory is not None:
            candidates = _setup_memory.rerank_candidates(candidates, dx.symptom)
        chosen = None
        for cand in candidates:
            section = cand["section"]
            if dx.tyre and dx.tyre not in section:
                continue
            cur = values.get(section, 0)
            delta, new_val = _catalog.validate_delta(section, cur, cand["delta"])
            if delta == 0:
                continue
            if not _setup_memory.approve_tweak(section, delta):
                continue
            chosen = SetupDelta(
                section, delta, cand.get("reason", ""),
                tier=cand.get("tier", "C"),
                old_value=cur, new_value=new_val,
            )
            break
        if chosen is None and candidates:
            cand = candidates[0]
            section = cand["section"]
            cur = values.get(section, 0)
            delta, new_val = _catalog.validate_delta(section, cur, cand["delta"])
            if delta != 0 and _setup_memory.approve_tweak(section, delta):
                chosen = SetupDelta(
                    section, delta, cand.get("reason", ""),
                    tier=cand.get("tier", "C"),
                    old_value=cur, new_value=new_val,
                )
        if chosen is None:
            continue

        if _apply_setup_delta(chosen, frame, symptom=dx.symptom, notify=False):
            ev = dx.evidence
            temp_c = ev.get("mean_temp_c", 0.0)
            agg = ev.get("aggression", 0.0)
            style_reason = (
                "Aggressive sliding is overheating the tyre — pressure first."
                if agg >= 0.55 and "hot" in dx.symptom
                else "Smooth style — camber and pressure to energize the tyre."
                if agg < 0.4 and "cold" in dx.symptom
                else "Core temperature outside the ideal window for this compound."
            )
            sign = "+" if chosen.delta >= 0 else ""
            state = "hot" if "hot" in dx.symptom else "cold"
            fb = _presenter.render("tyre_window", {
                "axle": dx.axle or "car",
                "state": state,
                "tyre": dx.tyre or dx.axle,
                "temp_c": int(round(temp_c)),
                "ideal_lo": _tyre_tracker.ideal_temp_range()[0],
                "ideal_hi": _tyre_tracker.ideal_temp_range()[1],
                "style_reason": style_reason,
                "section_name": chosen.section,
                "delta_sign": sign,
                "delta_abs": abs(chosen.delta),
                "reason": chosen.reason,
            })
            _remember_setup_tweak(
                chosen, source="tyre",
                why=fb.why,
                action=fb.action,
            )
            _active_tyre_symptoms.append(dx.symptom)
            _feedback.enqueue(fb)
            _archive.append_record({
                "record_type": "tyre_diagnosis",
                "lap": frame.lap,
                "symptom": dx.symptom,
                "tyre": dx.tyre,
                "axle": dx.axle,
                "evidence": ev,
                "setup_change": chosen.section,
            })
            return


def _coaching_allowed():
    return _volatility.coaching_allowed()


def _setup_tweaks_allowed():
    if _volatility.phase != PHASE_LEARNING:
        return True
    if _track_profile is not None and _track_profile.allows_setup_during_learning():
        return True
    return False


def _tyre_setup_allowed():
    if _volatility.phase != PHASE_LEARNING:
        return True
    if _track_profile is not None and _track_profile.allows_setup_during_learning():
        return True
    if _volatility.total_laps >= int(_thresholds.get("EARLY_COACHING_AFTER_LAPS", 2)):
        return _tyre_tracker.stint_ready()
    return False


def _on_corner_exit(event, frame):
    bucket = event.bucket
    corner = event.corner or "Corner"
    phase = event.phase or "mid"

    dyn = _dynamics.update(frame)
    bal = _balance.update(frame, dyn)
    yaw = _yaw_gates.classify(frame, dyn)
    inp = _baselines.input_deviation(bucket, frame.brake, frame.speed_kmh, frame.steer)

    summary = _corner_metrics.finalize(corner)
    if summary:
        _lap_corner_summaries[corner] = summary
    speed_class = _spline.corner_speed_class(corner) if _spline else "medium"
    landmarks = _spline.corner_landmarks(corner) if _spline else {}
    corner_cfg = _spline.corner_config(corner) if _spline else None
    line_ref = _line_ref.get(corner) if _line_ref is not None else {}
    corner_display = _spline.corner_display_name(corner) if _spline else corner
    chain_deltas = _build_chain_deltas()

    if _coaching_allowed() and summary and _line_analyzer is not None:
        line_issue = _line_analyzer.analyze(
            corner, summary, line_ref, landmarks,
            corner_cfg=corner_cfg, chain_deltas=chain_deltas,
            spline_indexer=_spline,
        )
        if line_issue is not None:
            ev = _enrich_feedback_evidence(dict(line_issue.evidence), corner)
            ev = _merge_input_focus(ev, getattr(line_issue, "input_focus", None))
            ev["corrections"] = ev.get("corrections", ev.get("steer_corrections", 0))
            line_hint = ev.get("line_hint") or landmarks.get("line_hint") or landmarks.get("approach", "")
            if not line_hint and corner_cfg:
                line_cfg = corner_cfg.get("line", {})
                line_hint = line_cfg.get("line_hint", line_cfg.get("compromise_note", ""))
            ev["line_hint"] = line_hint
            if ev.get("payoff_corner") and _spline is not None:
                ev["payoff_corner"] = _spline.corner_display_name(ev["payoff_corner"])
            template_key = getattr(line_issue, "template_key", None) or line_issue.issue
            _feedback.enqueue(_presenter.render(template_key, ev))

    if _coaching_allowed() and summary and _phase_pace is not None:
        pot_gap = _lap_analyzer.potential_gap_s(_lap_analyzer.last_lap_ms())
        micro = _phase_pace.next_gain(
            summary, line_ref, corner_display, pot_gap,
            line_cfg=_spline.corner_line(corner) if _spline else None,
        )
        if micro is not None:
            micro["phase"] = micro.get("phase", "mid").upper()
            micro["corner_name"] = corner_display
            _feedback.enqueue(_presenter.render("micro_gain", micro))

    hit = None
    if _symptom_detector is not None and summary:
        hit = _symptom_detector.primary(summary, speed_class)

    corner_delta_s = _lap_analyzer.corner_delta(corner) if _lap_analyzer else 0.0
    telem_ctx = build_telemetry_context(
        summary, bal, inp, corner_delta_s, hit, speed_class,
        _setup_memory, _thresholds,
    )

    symptom = hit.symptom if hit else _symptom_from_balance(bal)
    if hit and hit.phase not in ("any", ""):
        phase = hit.phase

    key = "%s:%s" % (corner, symptom)
    laps_persist = _decision._symptom_counts.get(key, 0)

    result = _decision.evaluate(
        yaw, inp, bal, corner=corner, phase=phase, symptom=symptom, lap=frame.lap,
        telemetry_context=telem_ctx,
    )

    if not _coaching_allowed() and not _setup_tweaks_allowed():
        return

    line_cfg = _spline.corner_line(corner) if _spline else None

    investigation = None
    if _coaching_allowed() and summary and _corner_investigator is not None:
        investigation = _corner_investigator.investigate(
            summary, line_ref, frame=frame, corner=corner,
            landmarks=landmarks, line_cfg=line_cfg, yaw_gate=yaw,
        )
        if investigation is not None:
            _archive.record_investigation(
                frame.lap, corner, investigation.phase, investigation,
            )

    if (
        _coaching_allowed()
        and yaw.gate == GATE_LOSS_OF_CONTROL
        and investigation is not None
    ):
        ev = _enrich_feedback_evidence(dict(investigation.evidence), corner)
        ev["phase"] = investigation.phase
        _feedback.enqueue(_presenter.render(investigation.template_key, ev))

    evidence = dict(result.evidence)
    if summary:
        evidence["phase_summary"] = summary
        evidence["surface"] = summary.get("surface", {})
    if hit:
        evidence["symptom_confidence"] = hit.confidence
        evidence.update(hit.evidence)

    _archive.append_record({
        "record_type": "corner_event",
        "lap": frame.lap,
        "corner": corner,
        "phase": phase,
        "symptom": symptom,
        "verdict": result.verdict,
        "input_score": result.input_score,
        "output_score": result.output_score,
        "telemetry_context": telem_ctx,
        "evidence": evidence,
    })

    if result.verdict == VERDICT_DRIVER_ERROR and _coaching_allowed():
        if hit is not None and hit.symptom in _SURFACE_SYMPTOMS:
            ev = _enrich_feedback_evidence(dict(hit.evidence), corner)
            ev.update(summary.get("surface", {}))
            ev = _merge_input_focus(ev, _surface_technique_focus(hit.symptom))
            _feedback.enqueue(_presenter.render(hit.symptom, ev))
        else:
            base_b = _baselines.get(bucket)
            clf = _driver_clf.classify(
                result, frame, base_b, corner,
                summary=summary, reference=line_ref,
                landmarks=landmarks, line_cfg=line_cfg, yaw_gate=yaw,
            )
            if clf is not None:
                ev = _enrich_feedback_evidence(clf.evidence, corner)
                ev["phase"] = phase
                _feedback.enqueue(_presenter.render(clf.template_key, ev))

    elif result.verdict in (VERDICT_SETUP_FLAW, VERDICT_SETUP_STABILIZE) and _setup_tweaks_allowed():
        base_ini = _find_base_setup(_track_folder)
        out_ini = _setup_writer.resolve_output_path(_track_folder)
        if base_ini and not os.path.isfile(out_ini):
            _setup_writer.clone_base(base_ini, out_ini)
        values = _read_setup_values(
            out_ini if os.path.isfile(out_ini) else base_ini
        )
        ctx = _setup_context(corner, symptom, telem_ctx)
        deltas = _setup_detector.detect(
            result, values, laps_persisting=laps_persist, context=ctx,
        )
        if deltas:
            _apply_setup_deltas(
                deltas, frame, corner=corner, phase=phase,
                symptom=symptom, result=result, telem_ctx=telem_ctx,
            )

    if _shift_analyzer is not None and corner and _setup_tweaks_allowed():
        shift_sym = _shift_analyzer.primary_corner_symptom(corner)
        if shift_sym:
            _maybe_apply_shift_setup(shift_sym, phase, frame, corner)

    if (
        _coaching_allowed()
        and _session_analyst is not None
        and _gg_envelope is not None
        and result.input_score < float(_thresholds.get("INPUT_SCORE_CLEAN", 0.3))
        and summary
        and summary.get("phases", {}).get("mid")
    ):
        grip_ev = _session_analyst.grip_coaching(
            frame.speed_kmh, frame.acc_g[1], _gg_envelope,
            _spline.corner_display_name(corner) if _spline else corner,
        )
        min_left = int(_thresholds.get("GRIP_COACH_MIN_LEFT_PCT", 3))
        if grip_ev and grip_ev.get("grip_left_pct", 0) >= min_left:
            grip_ev = _enrich_feedback_evidence(grip_ev, corner)
            _feedback.enqueue(_presenter.render("grip_left", grip_ev))


def _build_live_session_plan(digest):
    if _spline is None or _lap_analyzer is None:
        return None, 0.0
    worst = _lap_analyzer.worst_corners(
        min_delta_s=float(_thresholds.get("WORST_CORNER_MIN_DELTA_S", 0.02)),
        limit=2,
    )
    if not worst:
        return None, 0.0
    pot_gap = float(digest.get("potential_gap_s", 0)) if digest else 0.0
    items = []
    for name, delta in worst:
        cfg = _spline.corner_config(name) or {}
        display = _spline.corner_display_name(name)
        items.append({
            "corner": name,
            "corner_display": display,
            "loss_s": round(delta, 3),
            "drill": "Match your fastest segment at %s next lap." % display,
            "spline_start": float(cfg.get("spline_start", 0.0)),
            "spline_end": float(cfg.get("spline_end", 1.0)),
        })
    return items, pot_gap


def _on_lap_complete(lap, frame, lap_type=LAP_FLYING):
    global _lap_time_ms, _last_volatility_phase, _lap_corner_summaries
    global _session_flying_laps, _session_best_lap_ms, _shift_corner_counts
    counted = lap_type == LAP_FLYING
    prev_phase = _volatility.phase
    clean_fraction = 0.70
    if _track_profile is not None:
        clean_fraction = _track_profile.clean_fraction()
    if counted:
        _volatility.finish_lap(clean_fraction=clean_fraction)
        lap_was_clean = _volatility._last_lap_clean
    else:
        lap_was_clean = False
    _volatility.reset_lap(frame.lap + 1)
    _session.set_phase(_volatility.phase)
    if _volatility.phase != prev_phase:
        clean, target = _volatility.learning_progress()
        if _archive is not None:
            _archive.record_phase_change(
                prev_phase, _volatility.phase, lap,
                clean_laps=clean, total_laps=_volatility.total_laps,
            )
        _save_session_phase()
    _corner_phases.reset_lap()
    if _shift_analyzer is not None:
        _shift_analyzer.reset_lap()
    _shift_corner_counts = {}
    if _corner_metrics is not None:
        _corner_metrics.reset_lap()
    if _grip_map is not None:
        _grip_map.finish_lap(
            _lap_analyzer.bucket_deltas(),
            lap_was_clean,
        )

    _lap_time_ms = _completed_lap_time_ms(frame)

    if counted:
        _session_flying_laps += 1
        if _lap_time_ms > 0 and (
            _session_best_lap_ms == 0 or _lap_time_ms < _session_best_lap_ms
        ):
            _session_best_lap_ms = _lap_time_ms

    summary = _lap_analyzer.finish_lap(
        _lap_time_ms, _lap_analyzer._lap_bucket_speed, counted=counted,
    )
    if counted:
        _baselines.save(frame.track, async_write=True)

    clean, target = _volatility.learning_progress()
    if counted and _volatility.phase == PHASE_BASELINE_READY and prev_phase == PHASE_LEARNING:
        _feedback.enqueue(_presenter.render("learning", {
            "lap": clean, "target_laps": target, "variance_status": "LOW",
        }))
        _apply_remaining_bootstrap(frame)

    if (
        counted
        and _track_profile is not None
        and _volatility.phase == PHASE_LEARNING
        and _track_profile.should_bootstrap(_volatility.total_laps, _volatility.clean_laps)
    ):
        hint = _track_profile.next_bootstrap_hint()
        if hint is not None:
            _apply_bootstrap_hint(hint, frame)

    _last_volatility_phase = _volatility.phase
    if counted:
        _save_session_phase(frame.track)

    _sync_tyre_compound()
    tyre_diagnoses = _tyre_tracker.finish_lap() if counted else []
    _apply_tyre_diagnoses(tyre_diagnoses, frame)
    tyre_summary = _tyre_tracker.last_summary()
    tyre_style = tyre_summary.get("style", {})
    shift_summary = _shift_analyzer.lap_summary() if _shift_analyzer else {}

    out_ini = _setup_writer.resolve_output_path(_track_folder)
    _archive.flush_lap(
        lap, _lap_time_ms,
        setup_snapshot=_read_setup_values(out_ini),
        driving_style={
            "aggression": tyre_style.get("aggression", min(1.0, abs(_dynamics.beta_deg()) / 25.0)),
            "consistency": tyre_style.get("consistency", max(0.0, 1.0 - _lap_analyzer.consistency_sigma_ms() / 2000.0)),
            "slip_index": tyre_style.get("slip_index", 0.0),
            "tyres": tyre_summary.get("tyres", {}),
            "shift_summary": shift_summary,
        },
        corner_deltas=summary.get("corner_deltas"),
        sector_deltas=summary.get("sector_deltas"),
        lap_type=lap_type,
        phase=_volatility.phase,
        in_pit=frame.in_pit,
        counted=counted,
    )

    rec = None
    if counted:
        rec = _setup_memory.evaluate_pending(_metrics_snapshot(
            _lap_time_ms,
            corner=(_setup_memory._pending or {}).get("corner", ""),
            corner_deltas=summary.get("corner_deltas"),
        ))
    if rec is not None and _archive is not None:
        before = rec.get("before") or {}
        after = rec.get("after") or {}
        _archive.append_record({
            "record_type": "setup_evaluation",
            "tweak_id": rec.get("tweak_id", ""),
            "parameter": rec.get("parameter", ""),
            "status": rec.get("status", ""),
            "effectiveness": rec.get("effectiveness", 0.0),
            "lap": lap,
            "lap_time_delta_ms": after.get("lap_time_ms", 0) - before.get("lap_time_ms", 0),
            "corner": rec.get("corner", ""),
            "symptom": rec.get("symptom", ""),
        })
        if rec.get("status") == "reverted":
            _archive.note_setup_revert()
    if rec is not None and rec.get("status") == "reverted":
        _revert_setup_ini(rec)
        _feedback.enqueue(_presenter.render("setup_revert", {
            "section_name": rec.get("parameter", ""),
        }))
    elif rec is not None and rec.get("status") == "confirmed":
        param = rec.get("parameter", "")
        _feedback.enqueue(_presenter.render("setup_tweak", {
            "section_name": param,
            "delta_sign": "+" if rec.get("delta", 0) >= 0 else "",
            "delta_abs": abs(rec.get("delta", 0)),
            "reason": "Confirmed — lap time improved with this change.",
            "expected": "Keep this lever; it matches your driving style.",
        }))

    if _session_analyst is not None and _coaching_allowed() and counted:
        setup_note = ""
        if _last_setup_note:
            setup_note = _last_setup_note.get("section", "")
        digest = _session_analyst.summarize_lap(
            _lap_time_ms, _lap_analyzer, tyre_style,
            summary.get("corner_deltas"), lap_was_clean, setup_note,
        )
        min_gap = float(_thresholds.get("LAP_DIGEST_MIN_POTENTIAL_GAP_S", 0.08))
        if digest and float(digest.get("potential_gap_s", 0)) >= min_gap:
            _feedback.enqueue(_presenter.render("lap_digest", digest))
        worst = _lap_analyzer.worst_corners(
            min_delta_s=float(_thresholds.get("WORST_CORNER_MIN_DELTA_S", 0.01)),
            limit=1,
        )
        if worst and lap_was_clean:
            name, delta = worst[0]
            display = _spline.corner_display_name(name) if _spline else name
            pot_ms = _lap_analyzer.theoretical_best_ms()
            _feedback.enqueue(_presenter.render("potential_gain", {
                "worst_corner": display,
                "worst_delta_s": "%.2f" % delta,
                "potential_lap": digest.get("potential_lap", "") if digest else "",
                "potential_gap_s": digest.get("potential_gap_s", "0") if digest else "0",
                "reason": "Your own reference data — no alien lap used.",
                "gain_action": "Match your fastest segment at %s next lap." % display,
            }))
        plan_items, plan_gap = _build_live_session_plan(digest or {})
        if plan_items and lap_was_clean:
            _archive.record_session_plan(plan_items, plan_gap)
            corners_txt = "; ".join(
                "%s (+%.2fs)" % (it["corner_display"], it["loss_s"]) for it in plan_items
            )
            _feedback.enqueue(_presenter.render("session_plan", {
                "potential_gap_s": "%.2f" % plan_gap,
                "corner_list": corners_txt,
                "primary_drill": plan_items[0].get("drill", ""),
                "item1_corner": plan_items[0]["corner_display"],
                "item1_loss": "%.2f" % plan_items[0]["loss_s"],
                "item2_corner": plan_items[1]["corner_display"] if len(plan_items) > 1 else "",
            }))

    if _line_ref is not None:
        corner_deltas = summary.get("corner_deltas", {})
        for corner, cs in _lap_corner_summaries.items():
            _line_ref.update_corner(corner, cs, corner_deltas.get(corner, 0.0))
    if _spline is not None and _line_analyzer is not None and _coaching_allowed():
        engine = _line_analyzer._engine
        for chain in _spline.line_chains():
            cid = chain.get("id", "")
            digest = engine.chain_summary(
                cid, chain, summary.get("corner_deltas", {}), _spline,
            )
            if digest is None:
                continue
            min_chain = float(_thresholds.get("CHAIN_DIGEST_MIN_DELTA_S", 0.08))
            if float(digest.get("total_delta_s", 0)) >= min_chain:
                digest["chain_id"] = cid.replace("_", " ")
                _feedback.enqueue(_presenter.render("chain_digest", digest))
    _lap_corner_summaries = {}

    _lap_analyzer.reset_lap(frame.lap + 1)


def _on_pit_entry(lap, frame):
    if _archive is not None:
        _archive.record_pit_transition("entry", lap, frame.spline)
    _flush_pit_tweak_queue(frame)
    if _setup_writer is not None:
        out_ini, setup_err = _setup_writer.ensure_auto_tweak(_track_folder)
        if setup_err and _archive is not None:
            _archive.append_record({
                "record_type": "setup_apply_failed",
                "lap": lap,
                "section": "pit_bootstrap",
                "reason": setup_err,
                "track_folder": _track_folder,
                "out_ini": out_ini or _setup_writer.resolve_output_path(_track_folder),
                "setups_root": _setup_writer._documents_setups_dir(),
            })
        _apply_remaining_bootstrap(frame, force_immediate=True)
    tick = _feedback.tick(0, safe_for_audio=True, in_pit=True)
    for ev in tick.get("dispatched", []):
        _archive.record_feedback(ev)


def _on_pit_exit(lap, frame):
    if _archive is not None:
        _archive.record_pit_transition("exit", lap, frame.spline)


def _on_hud_render(deltaT):
    if _hud_snapshot is not None and not _hud_snapshot.in_pit:
        draw_hud(_hud_snapshot)


def _set_ui_text(key, text):
    label = _ui_labels.get(key)
    if label is None:
        return
    if _ui_text_cache.get(key) == text:
        return
    _ui_text_cache[key] = text
    ac.setText(label, text)


def _add_label(app_window, key, x, y, font_size, align="left", color=None):
    label = ac.addLabel(app_window, "")
    ac.setPosition(label, x, y)
    ac.setFontSize(label, font_size)
    if hasattr(ac, "setFontAlignment"):
        ac.setFontAlignment(label, align)
    if hasattr(ac, "setFontColor"):
        rgba = color or (1.0, 1.0, 1.0, 1.0)
        ac.setFontColor(label, rgba[0], rgba[1], rgba[2], rgba[3])
    if hasattr(ac, "setFontOutline"):
        ac.setFontOutline(label, 1)
    _ui_labels[key] = label
    return label


def _set_label_color(key, rgba):
    label = _ui_labels.get(key)
    if label and hasattr(ac, "setFontColor"):
        ac.setFontColor(label, rgba[0], rgba[1], rgba[2], rgba[3])


def _build_dashboard_ui(app_window):
    tx, col_w = LBL_TYRE_COLS

    _add_label(app_window, "learn_line", LBL_LEARN[0], LBL_LEARN[1], 12)
    _add_label(app_window, "learn_detail", LBL_LEARN_DETAIL[0], LBL_LEARN_DETAIL[1], 11,
               color=(0.88, 0.9, 0.95, 1.0))
    _add_label(app_window, "setup_line", LBL_SETUP[0], LBL_SETUP[1], 11,
               color=(0.25, 0.9, 0.45, 1.0))
    _add_label(app_window, "speed_val", LBL_SPEED[0], LBL_SPEED[1], 28, "right")
    _add_label(app_window, "speed_unit", LBL_SPEED_UNIT[0], LBL_SPEED_UNIT[1], 12,
               color=(0.9, 0.9, 0.92, 1.0))
    _add_label(app_window, "delta_val", LBL_DELTA[0], LBL_DELTA[1], 16, "right")

    for i, name in enumerate(("lf", "rf", "lr", "rr")):
        x = tx + i * col_w
        _add_label(app_window, "tyre_%s_tag" % name, x, LBL_TYRE_TAG_Y, 11,
                   color=(0.85, 0.85, 0.9, 1.0))
        _set_ui_text("tyre_%s_tag" % name, name.upper())
        _add_label(app_window, "tyre_%s_val" % name, x + 22, LBL_TYRE_VAL_Y, 18)

    _add_label(app_window, "status_line", LBL_STATUS[0], LBL_STATUS[1], 18)
    _add_label(app_window, "coach_hint", LBL_COACH[0], LBL_COACH[1], 12,
               color=(0.75, 0.85, 1.0, 1.0))
    _add_label(app_window, "feedback_line", LBL_FEEDBACK[0], LBL_FEEDBACK[1], 13,
               color=(1.0, 0.88, 0.3, 1.0))

    _add_label(app_window, "cue1", LBL_CUE1[0], LBL_CUE1[1], 24, "right",
               color=(1.0, 0.88, 0.2, 1.0))
    _add_label(app_window, "cue2", LBL_CUE2[0], LBL_CUE2[1], 20, "right")

    y = LBL_PIT_Y
    _add_label(app_window, "pit_header", 8, y, 13)
    _add_label(app_window, "pit_setup", 8, y + 16, 11, color=(0.25, 0.9, 0.45, 1.0))
    _add_label(app_window, "pit_hint", 8, y + 32, 12)
    _add_label(app_window, "pit_action", 8, y + 48, 12)
    _add_label(app_window, "pit_coach", 8, y + 64, 13, color=(1.0, 1.0, 0.6, 1.0))
    _add_label(app_window, "pit_grip", 8, y + 82, 11, color=(0.55, 0.85, 1.0, 1.0))


def _update_hud_labels(snap):
    _set_ui_text("learn_line", format_learn_line(snap))
    _set_ui_text("learn_detail", format_learn_detail(snap))

    setup_txt = format_setup_hud_line(snap.setup_note)
    _set_ui_text("setup_line", setup_txt)
    if setup_txt:
        _set_label_color("setup_line", (0.25, 0.9, 0.45, 1.0))

    spd = int(round(snap.speed_kmh))
    _set_ui_text("speed_val", str(spd))
    _set_ui_text("speed_unit", "km/h")

    dtext, dcolor = format_delta(snap.lap_delta_s)
    _set_ui_text("delta_val", dtext)
    _set_label_color("delta_val", dcolor)

    temps = snap.tyre_temps
    for i, name in enumerate(("lf", "rf", "lr", "rr")):
        temp = temps[i] if i < len(temps) else 0.0
        val_key = "tyre_%s_val" % name
        if temp > 0:
            _set_ui_text(val_key, "%d\xb0" % int(round(temp)))
        else:
            _set_ui_text(val_key, "--")
        _set_label_color(val_key, temp_font_color(
            temp, snap.tyre_ideal_lo, snap.tyre_ideal_hi,
            snap.tyre_hot_c, snap.tyre_cold_c,
        ))

    if not snap.in_pit:
        _set_ui_text("status_line", format_phase_line(snap))
        if snap.cue_id and snap.cue_alpha > 0.1:
            _set_label_color("status_line", (1.0, 0.85, 0.25, 1.0))
        else:
            _set_label_color("status_line", (0.92, 0.92, 0.95, 1.0))

        hint = format_coach_hint(snap)
        _set_ui_text("coach_hint", hint)

        fb = format_feedback_line(snap)
        _set_ui_text("feedback_line", fb)
        if fb:
            _set_label_color("feedback_line", feedback_type_color(snap.feedback_type))
        else:
            _set_label_color("feedback_line", (0.75, 0.75, 0.8, 1.0))
    else:
        _set_ui_text("status_line", "")
        _set_ui_text("coach_hint", "")
        _set_ui_text("feedback_line", "")


def _update_cue_labels(cue_id, corner, alpha, in_pit):
    if in_pit or not cue_id or alpha < 0.08:
        _set_ui_text("cue1", "")
        _set_ui_text("cue2", "")
        return
    _, line1, line2 = cue_style(cue_id)
    _set_ui_text("cue1", line1)
    _set_ui_text("cue2", line2 or corner[:12].upper())


def _update_dashboard(frame, corner, phase_name, balance, tick_result, deltaT):
    global _hud_snapshot, _cue_alpha, _last_in_pit

    in_pit = frame.in_pit
    if in_pit != _last_in_pit:
        _last_in_pit = in_pit
        ac.setSize(_app_window, _HUD_W, LBL_PIT_Y + 102 if in_pit else _HUD_H)

    if tick_result.get("cue"):
        _cue_alpha = 1.0
    else:
        _cue_alpha = max(0.0, _cue_alpha - deltaT * 1.2)

    track_display = _spline.display_name or (
        _spline.track_id.replace("_", " ").title() if _spline.track_id else frame.track
    )
    landmarks = _spline.corner_landmarks(corner) if corner else {}
    upcoming = _spline.upcoming_corner(frame.spline) if not corner else None
    bootstrap_active = (
        _track_profile is not None and _track_profile.bootstrap_active
    )
    thresholds = _tyre_tracker.temp_thresholds()
    grip_segments = []
    grip_hint = ""
    grip_zone = ""
    if _grip_map is not None:
        grip_segments = _grip_map.segment_ratings()
        ref = _grip_map.at_spline(frame.spline)
        grip_zone = ref.zone
        grip_hint = _grip_map.current_hint(
            frame.spline,
            _spline.corner_display_name(corner) if corner else "",
        )
    _hud_snapshot = build_snapshot(
        frame=frame,
        spline_indexer=_spline,
        corner_name=corner,
        phase_name=phase_name,
        volatility=_volatility,
        tyre_temps=frame.tyre_temp,
        tyre_thresholds=thresholds,
        lap_delta_s=_lap_analyzer.current_lap_delta_s(),
        cue_id=tick_result.get("cue", ""),
        cue_corner=tick_result.get("cue_corner", ""),
        cue_alpha=_cue_alpha,
        in_pit=in_pit,
        width=_HUD_W,
        height=_HUD_H,
        track_name=track_display,
        consistency_pct=_volatility.lap_consistency_pct(),
        bootstrap_active=bootstrap_active,
        landmarks=landmarks,
        upcoming_corner=upcoming,
        feedback_headline=tick_result.get("headline_short", ""),
        feedback_type=tick_result.get("feedback_type", ""),
        feedback_alpha=tick_result.get("feedback_alpha", 0.0),
        setup_note=_last_setup_note,
        potential_gap_s=_lap_analyzer.potential_gap_s(_lap_analyzer.last_lap_ms()),
        grip_segments=grip_segments,
        grip_hint=grip_hint,
        grip_zone=grip_zone,
        shift_line=_shift_analyzer.hud_line() if _shift_analyzer else "",
        last_lap_ms=_lap_analyzer.last_lap_ms(),
        pit_queue_count=_pit_queue_count(),
    )

    if not in_pit:
        _update_hud_labels(_hud_snapshot)
        _update_cue_labels(
            tick_result.get("cue", ""),
            tick_result.get("cue_corner", ""),
            _cue_alpha,
            in_pit,
        )
    else:
        for key in (
            "learn_line", "learn_detail", "setup_line", "speed_val", "speed_unit", "delta_val",
            "tyre_lf_val", "tyre_rf_val", "tyre_lr_val", "tyre_rr_val",
            "status_line", "coach_hint", "feedback_line", "cue1", "cue2",
        ):
            _set_ui_text(key, "")

    if not in_pit:
        for key in ("pit_header", "pit_setup", "pit_hint", "pit_action", "pit_coach", "pit_grip"):
            _set_ui_text(key, "")
        return

    clean, target = _volatility.learning_progress()
    landmarks = _spline.corner_landmarks(corner) if corner else {}
    upcoming = _spline.upcoming_corner(frame.spline) if not corner else None
    sector = _spline.sector_name(frame.spline)
    track_display = _spline.display_name or (
        _spline.track_id.replace("_", " ").title() if _spline.track_id else frame.track
    )
    style = _tyre_tracker.driving_style()
    if _tyre_tracker.last_summary().get("style"):
        style = _tyre_tracker.last_summary().get("style")

    lines = _dashboard.build(
        frame=frame,
        phase=_volatility.phase,
        clean_laps=clean,
        target_laps=target,
        total_laps=_volatility.total_laps,
        spline_indexer=_spline,
        corner_name=corner,
        corner_display=_spline.corner_display_name(corner) if corner else "",
        phase_name=phase_name,
        landmarks=landmarks,
        upcoming_corner=upcoming,
        sector=sector,
        lap_delta_s=_lap_analyzer.current_lap_delta_s(),
        worst_corners=_lap_analyzer.worst_corners(min_delta_s=0.03, limit=1),
        reference_lap_ms=_lap_analyzer.reference_lap_ms(),
        theoretical_best_ms=_lap_analyzer.theoretical_best_ms(),
        last_lap_ms=_lap_analyzer.last_lap_ms(),
        tyre_temps=frame.tyre_temp,
        tyre_ideal_lo=thresholds["ideal_lo"],
        tyre_ideal_hi=thresholds["ideal_hi"],
        tyre_hot_c=thresholds["hot_c"],
        tyre_cold_c=thresholds["cold_c"],
        driving_style=style,
        balance=balance,
        bootstrap_active=_track_profile is not None and _track_profile.bootstrap_active,
        track_display=track_display,
        coach_text=tick_result.get("ticker", ""),
        bucket_consistent=_volatility.lap_consistency_pct(),
        coaching_active=_volatility.coaching_allowed(),
        stint_ready=_tyre_tracker.stint_ready(),
    )
    _set_ui_text("pit_header", lines["header"])
    pit_setup = format_setup_pit_detail(_last_setup_note)
    _set_ui_text("pit_setup", pit_setup)
    _set_ui_text("pit_hint", lines["hint"])
    _set_ui_text("pit_action", lines["pace"])
    _set_ui_text("pit_coach", tick_result.get("ticker") or lines["coach"])
    if _grip_map is not None and _grip_map.has_data():
        _set_ui_text("pit_grip", _grip_map.pit_summary(_spline))
    else:
        _set_ui_text("pit_grip", format_grip_legend())


def acMain(ac_version):
    global _app_window
    try:
        _init_modules()
    except Exception:
        _log_boot_error("acMain init")
        raise

    app_name = "Virtual Race Engineer"
    _app_window = ac.newApp(app_name)
    ac.setTitle(_app_window, "")
    ac.setSize(_app_window, _HUD_W, _HUD_H)
    ac.setPosition(_app_window, 20, 20)
    ac.drawBorder(_app_window, 0)
    ac.setBackgroundOpacity(_app_window, 0.92)

    _build_dashboard_ui(_app_window)
    ac.addRenderCallback(_app_window, _on_hud_render)

    if hasattr(ac, "ext_setStrictMode"):
        ac.ext_setStrictMode()

    return app_name


def _shutdown():
    global _initialized, _archive, _baselines, _setup_memory, _last_track, _pit_tweak_queue
    if _archive is not None and _archive.session_dir:
        try:
            phase = _volatility.phase if _volatility is not None else "LEARNING"
            _archive.end_session(
                _session_flying_laps, _session_best_lap_ms, phase=phase,
            )
        except Exception:
            pass
    _save_session_phase()
    if _baselines is not None and _last_track:
        try:
            _baselines.save(_last_track)
        except Exception:
            pass
    if _setup_memory is not None:
        try:
            _setup_memory.save()
        except Exception:
            pass
    if _grip_map is not None:
        try:
            _grip_map.save()
        except Exception:
            pass
    _initialized = False
    _last_track = ""
    _pit_tweak_queue = []


def ext_acReload():
    """CSP live reload (Content Manager → CSP → Python Apps Debug)."""
    _shutdown()


def acShutdown():
    _shutdown()


def acUpdate(deltaT):
    global _last_track, _track_folder, _session_flying_laps, _session_best_lap_ms

    if not _initialized:
        _init_modules()

    frame = _ingest.sample(deltaT)

    if frame.track and frame.track != _last_track:
        _last_track = frame.track
        _load_track(frame.track)
        _session_flying_laps = 0
        _session_best_lap_ms = 0
        _archive.start_session(frame.track, frame.car, _volatility.phase)
        _apply_remaining_bootstrap(frame)
    elif frame.track and _archive is not None and _archive.session_dir is None:
        _archive.start_session(frame.track, frame.car, _volatility.phase)

    bucket = _spline.bin(frame.spline)
    corner = _spline.corner_name(frame.spline)
    phase_name = _corner_phases.current_phase(corner, frame)

    _volatility.observe(bucket, frame.speed_kmh, frame.steer, frame.brake)
    dyn = _dynamics.update(frame)
    bal = _balance.update(frame, dyn)
    _lap_analyzer.observe(bucket, frame.speed_kmh, deltaT)

    if _volatility.phase != PHASE_LEARNING:
        _baselines.observe(bucket, frame.brake, frame.speed_kmh, frame.steer)

    if not frame.in_pit and frame.speed_kmh > 40.0:
        if _gg_envelope is not None:
            _gg_envelope.observe(frame.speed_kmh, frame.acc_g[1])
        if _corner_metrics is not None:
            _corner_metrics.observe(corner, phase_name, frame, dyn, bal)
        if _grip_map is not None:
            _grip_map.observe(bucket, frame, bal)
        if _shift_analyzer is not None:
            shift_evt = _shift_analyzer.observe(frame, corner, phase_name, dyn)
            if shift_evt is not None:
                _handle_shift_event(shift_evt)

    _session.update(frame, _spline, _corner_phases)

    _sync_tyre_compound()
    _tyre_tracker.observe(frame)

    safe = _ingest.is_safe_for_audio(frame)
    tick = _feedback.tick(deltaT, safe_for_audio=safe, in_pit=frame.in_pit)

    _update_dashboard(frame, corner, phase_name, bal, tick, deltaT)

    _archive.observe_frame(frame, corner, phase_name, dyn, bal)
