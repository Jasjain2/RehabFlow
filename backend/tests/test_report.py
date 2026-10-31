from core.report import compute_xp, earned_badges, posture_check, symmetry_summary


def test_posture_check_rules_override_ml_at_rehab_depth():
    assert posture_check(None, 90) is None
    assert posture_check("good", 50) == "good"
    assert posture_check("bad", 85) == "acceptable_for_rehab_depth"
    assert posture_check("bad", 80) == "needs_attention"


def test_xp():
    assert compute_xp(0, 0, False) == 0
    assert compute_xp(10, 70, False) == 100
    assert compute_xp(10, 85, True) == 100 + 50 + 100


def test_badges():
    assert earned_badges(0, 0, 0, False, True) == []
    assert earned_badges(12, 92, 0, True, True) == ["First Session", "Plan Complete", "Form Master", "Steady Pace"]
    assert earned_badges(12, 70, 2, False, False) == []


def test_symmetry_summary_averages_measured_reps():
    assert symmetry_summary([{"knee": 10, "hip": 4}, {"knee": 14}, {}]) == {"knee": 12.0, "hip": 4.0}
