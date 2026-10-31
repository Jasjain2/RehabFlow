import math

import pytest

from tracking.analyzer import (
    Landmark,
    SIDES,
    calculate_angle,
    compute_angles,
    score_frame,
    trunk_lean,
)

SQUAT_STANDING_IDEAL = {"knee_flexion": 170, "hip_flexion": 170, "trunk_lean": 5}
PUSHUP_UP_IDEAL = {"elbow_flexion": 170, "shoulder_flexion": 70, "body_straightness": 170}


def test_perfect_form_scores_100():
    result = score_frame("squat", "standing", SQUAT_STANDING_IDEAL)
    assert result.score == 100
    assert all(d == 0 for d in result.deviations.values())


def test_one_degree_outside_loses_2_points():
    result = score_frame("squat", "standing", {**SQUAT_STANDING_IDEAL, "knee_flexion": 164})
    assert result.joint_scores["knee_flexion"] == 98
    assert result.deviations["knee_flexion"] == -1
    assert result.score == pytest.approx((98 + 100 + 100) / 3)


def test_10_degrees_outside_loses_20_points():
    result = score_frame("squat", "standing", {**SQUAT_STANDING_IDEAL, "trunk_lean": 20})
    assert result.joint_scores["trunk_lean"] == 80
    assert result.deviations["trunk_lean"] == 10


def test_minimum_score_is_zero():
    result = score_frame("squat", "standing", {"knee_flexion": 0, "hip_flexion": 0, "trunk_lean": 90})
    assert result.score == 0
    assert all(s == 0 for s in result.joint_scores.values())


def test_squat_uses_squat_joints():
    angles = {**SQUAT_STANDING_IDEAL, "elbow_flexion": 10, "knee_valgus": 40}
    result = score_frame("squat", "standing", angles)
    # knee_valgus is tracked but has no ideal range, so it isn't scored
    assert set(result.joint_scores) == {"knee_flexion", "hip_flexion", "trunk_lean"}
    assert result.score == 100


def test_pushup_uses_pushup_joints():
    result = score_frame("push_up", "up", {**PUSHUP_UP_IDEAL, "knee_flexion": 10})
    assert set(result.joint_scores) == {"elbow_flexion", "shoulder_flexion", "body_straightness"}
    assert result.score == 100


def test_different_phases_have_different_ideals():
    bottom_angles = {"knee_flexion": 85, "hip_flexion": 75, "trunk_lean": 20}
    assert score_frame("squat", "bottom", bottom_angles).score == 100
    assert score_frame("squat", "standing", bottom_angles).score < 100


def test_missing_and_nan_angles_are_skipped():
    result = score_frame("squat", "standing", {"knee_flexion": 170, "hip_flexion": math.nan})
    assert set(result.joint_scores) == {"knee_flexion"}
    assert score_frame("squat", "standing", {}) is None


def test_unknown_exercise_or_phase_raises():
    with pytest.raises(ValueError):
        score_frame("lunge", "standing", SQUAT_STANDING_IDEAL)
    with pytest.raises(ValueError):
        score_frame("squat", "up", SQUAT_STANDING_IDEAL)


def test_calculate_angle_right_and_straight():
    assert calculate_angle(Landmark(0, 0), Landmark(0, 1), Landmark(1, 1)) == pytest.approx(90)
    assert calculate_angle(Landmark(0, 0), Landmark(0, 1), Landmark(0, 2)) == pytest.approx(180)
    assert math.isnan(calculate_angle(Landmark(0, 0), Landmark(0, 0), Landmark(1, 1)))


def test_trunk_lean_upright_and_leaning():
    assert trunk_lean(Landmark(0.5, 0.2), Landmark(0.5, 0.5)) == pytest.approx(0)
    assert trunk_lean(Landmark(0.8, 0.2), Landmark(0.5, 0.5)) == pytest.approx(45)


def _standing_pose(right_visibility: float = 1.0) -> list[Landmark]:
    """Upright person facing the camera, legs straight, arms hanging."""
    landmarks = [Landmark(0.5, 0.5)] * 33
    for side, x in (("left", 0.6), ("right", 0.4)):
        vis = right_visibility if side == "right" else 1.0
        coords = {"shoulder": 0.2, "elbow": 0.35, "wrist": 0.5, "hip": 0.5, "knee": 0.7, "ankle": 0.9}
        for joint, y in coords.items():
            landmarks[SIDES[side][joint]] = Landmark(x, y, vis)
    return landmarks


def test_compute_angles_standing_pose():
    angles = compute_angles(_standing_pose())
    assert angles["knee_flexion"] == pytest.approx(180)
    assert angles["hip_flexion"] == pytest.approx(180)
    assert angles["trunk_lean"] == pytest.approx(0)
    assert angles["knee_valgus"] == pytest.approx(0)
    assert angles["knee_flexion_asymmetry"] == pytest.approx(0)
    assert score_frame("squat", "standing", angles).score == 100


def test_compute_angles_uses_visible_side_when_other_occluded():
    landmarks = _standing_pose(right_visibility=0.1)
    # Bend the occluded right knee; the visible left side should win
    landmarks[SIDES["right"]["knee"]] = Landmark(0.3, 0.7, 0.1)
    angles = compute_angles(landmarks)
    assert angles["knee_flexion"] == pytest.approx(180)
    assert angles["knee_flexion_asymmetry"] > 0


def test_knee_valgus_positive_when_knee_caves_in():
    landmarks = _standing_pose()
    # Move the left knee (x=0.6) toward the midline (x=0.5)
    landmarks[SIDES["left"]["knee"]] = Landmark(0.55, 0.7)
    landmarks[SIDES["right"]["knee"]] = Landmark(0.45, 0.7)
    assert compute_angles(landmarks)["knee_valgus"] > 0


def test_compute_angles_rejects_wrong_landmark_count():
    with pytest.raises(ValueError):
        compute_angles([Landmark(0, 0)] * 10)
