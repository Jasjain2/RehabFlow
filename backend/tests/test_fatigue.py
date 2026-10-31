import pytest

from tracking.fatigue import FatigueDetector


def detector_with_baseline(scores=(90, 100, 110)) -> FatigueDetector:
    detector = FatigueDetector()
    for score in scores:
        detector.update(score)
    return detector


def test_baseline_from_first_three_reps():
    assert detector_with_baseline((80, 90, 100)).baseline == pytest.approx(90)


def test_building_baseline_state():
    detector = FatigueDetector()
    assert [detector.update(s) for s in (90, 80, 70)] == ["building_baseline"] * 3
    assert detector.update(80) != "building_baseline"


def test_no_alert_under_15_percent():
    detector = detector_with_baseline()
    assert detector.update(86) == "normal"
    assert detector.current_drift == pytest.approx(0.14)


def test_moderate_alert_at_15_percent():
    assert detector_with_baseline().update(85) == "moderate"


def test_high_alert_at_30_percent():
    assert detector_with_baseline().update(70) == "high"


def test_threshold_exact_despite_float_error():
    # (80 - 68) / 80 is exactly 0.15 but can evaluate just below it in floating point
    assert detector_with_baseline((80, 80, 80)).update(68) == "moderate"


def test_improvement_is_normal_and_max_drift_tracked():
    detector = detector_with_baseline()
    assert detector.update(110) == "normal"
    assert detector.current_drift < 0
    detector.update(80)
    detector.update(95)
    assert detector.max_drift == pytest.approx(0.20)


def test_zero_baseline_does_not_divide_by_zero():
    assert detector_with_baseline((0, 0, 0)).update(0) == "normal"
