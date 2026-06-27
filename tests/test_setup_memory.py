from setup_memory import SetupMemory, STATUS_CONFIRMED
from setup_detector import SetupDelta


def test_effectiveness_confirm(tmp_path, thresholds):
    mem = SetupMemory(data_dir=str(tmp_path), thresholds=thresholds)
    mem.track_id = "monza"
    delta = SetupDelta("WING_1", 1, "test", old_value=20, new_value=21)
    mem.record_pending(delta, lap=5, before={"lap_time_ms": 95000, "corner_delta": 0.2})
    result = mem.evaluate_pending({
        "lap_time_ms": 94500,
        "corner_delta": 0.1,
        "symptom_metric": 0.5,
    })
    assert result["status"] == STATUS_CONFIRMED
