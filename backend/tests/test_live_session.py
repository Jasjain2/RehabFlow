import pytest

from config.settings import MODELS_DIR, SIGNAL_CONSECUTIVE_FRAMES
from core.schema import Exercise, RehabPlan
from tests.poses import PUSHUP_REP, SQUAT_REP, pushup_pose, squat_pose
from tracking.analyzer import SIDES, compute_angles
from tracking.live_session import Debounce, LiveSession, rep_coaching_payload
from tracking.ml import MLModels

FRAME_S = 0.4


@pytest.fixture(scope="module")
def models():
    return MLModels(MODELS_DIR)


def make_plan(*exercises: tuple[str, int, int]) -> RehabPlan:
    return RehabPlan(
        exercises=[
            Exercise(name=name, sets=sets, reps_per_set=reps, rest_seconds=30, coaching_cues=[], safety_warnings=[])
            for name, sets, reps in exercises
        ],
        warmup="w", cooldown="c", overall_safety="s",
    )


class Driver:
    def __init__(self, live: LiveSession):
        self.live = live
        self.now = 0.0
        self.results = []

    def frame(self, landmarks):
        self.now += FRAME_S
        result = self.live.process_frame(landmarks, self.now)
        self.results.append(result)
        return result

    def squat_reps(self, count: int):
        for _ in range(count):
            for angle in SQUAT_REP:
                self.frame(squat_pose(angle))
        return self.results[-1]


def test_test_poses_have_the_intended_angles():
    assert compute_angles(squat_pose(90))["knee_flexion"] == pytest.approx(90)
    assert compute_angles(squat_pose(175, trunk_lean=20))["trunk_lean"] == pytest.approx(20)
    assert compute_angles(pushup_pose(95))["elbow_flexion"] == pytest.approx(95)


def test_squat_rep_is_counted_scored_and_tagged_by_ml(models):
    driver = Driver(LiveSession(make_plan(("squat", 1, 3)), models))
    last = driver.squat_reps(1)
    rep = last.completed_rep
    assert rep is not None and rep.rep_number == 1 and rep.set_number == 1
    assert 0 <= rep.form_score <= 100
    assert rep.fatigue_level == "building_baseline"
    assert rep.ml_form_quality in ("good", "bad")
    assert rep.posture_check in ("good", "needs_attention", "acceptable_for_rehab_depth")
    assert last.update.rep_count == 1 and last.update.rep_in_set == 1
    assert last.update.ml_phase is not None and 0 <= last.update.ml_phase_confidence <= 1
    assert last.update.ml_form_quality == rep.ml_form_quality
    # Rule-based phase drives the counter regardless of what the ML model says
    assert last.update.phase == "standing"


def test_set_completion_starts_rest_then_next_set(models):
    driver = Driver(LiveSession(make_plan(("squat", 2, 2)), models))
    last = driver.squat_reps(2)
    assert last.completed_set is not None
    assert [r.rep_number for r in last.completed_set.reps] == [1, 2]
    assert last.update.status == "resting"
    assert last.update.rest_seconds_remaining == 30

    resting = driver.frame(squat_pose(120))
    assert resting.update.form_score is None and resting.completed_rep is None
    assert resting.update.landmarks is not None

    driver.now += 30
    resumed = driver.frame(squat_pose(175))
    assert resumed.update.status == "exercising"
    assert resumed.update.set_number == 2 and resumed.update.rep_in_set == 0


def test_coaching_shows_only_during_matching_rest(models):
    driver = Driver(LiveSession(make_plan(("squat", 2, 1)), models))
    completed = driver.squat_reps(1).completed_set
    driver.live.set_coaching(completed.key, "Keep your chest up.")
    assert driver.frame(squat_pose(175)).update.set_coaching == "Keep your chest up."
    driver.live.skip_rest()
    assert driver.frame(squat_pose(175)).update.set_coaching is None


def test_session_completes_after_last_set_and_advances_exercises(models):
    driver = Driver(LiveSession(make_plan(("squat", 1, 1), ("push_up", 1, 1)), models))
    last = driver.squat_reps(1)
    assert last.update.status == "resting" and last.completed_set is not None
    driver.live.skip_rest()
    for angle in PUSHUP_REP:
        result = driver.frame(pushup_pose(angle))
    assert result.completed_rep.exercise == "push_up"
    # No trained models for push-ups: ML fields stay empty
    assert result.completed_rep.ml_form_quality is None and result.update.ml_phase is None
    assert result.update.status == "complete"
    assert result.completed_set is None  # no rest, so no coaching after the final set


def test_no_person_detected(models):
    result = Driver(LiveSession(make_plan(("squat", 1, 1)), models)).frame(None)
    assert result.update.form_score is None and result.update.landmarks is None


def test_asymmetry_flagged_after_consecutive_frames(models):
    driver = Driver(LiveSession(make_plan(("squat", 1, 5)), models))
    flags = [driver.frame(squat_pose(175, right_knee_angle=150)).update for _ in range(SIGNAL_CONSECUTIVE_FRAMES)]
    assert [u.asymmetry_detected for u in flags] == [False] * (SIGNAL_CONSECUTIVE_FRAMES - 1) + [True]
    assert flags[-1].asymmetry_details["knee"] == pytest.approx(25, abs=0.5)


def test_occluded_side_is_not_asymmetry(models):
    driver = Driver(LiveSession(make_plan(("squat", 1, 5)), models))
    for _ in range(SIGNAL_CONSECUTIVE_FRAMES + 2):
        update = driver.frame(squat_pose(175, right_knee_angle=150, right_visibility=0.2)).update
    assert not update.asymmetry_detected


def test_rep_records_asymmetry_and_coaching_payload(models):
    driver = Driver(LiveSession(make_plan(("squat", 2, 1)), models))
    for angle in SQUAT_REP:
        result = driver.frame(squat_pose(angle, right_knee_angle=angle - 12))
    assert result.completed_rep.asymmetry["knee"] == pytest.approx(12, abs=1)
    payload = rep_coaching_payload(result.completed_set)
    assert payload["exercise"] == "squat" and payload["set_number"] == 1
    assert payload["reps"][0]["lowest_joint"] in result.completed_rep.joint_scores


def test_runs_rule_based_only_without_models():
    driver = Driver(LiveSession(make_plan(("squat", 1, 1)), None))
    result = driver.squat_reps(1)
    assert result.completed_rep.ml_form_quality is None and result.completed_rep.posture_check is None
    assert result.update.status == "complete"


def test_debounce():
    debounce = Debounce(3)
    assert [debounce.update(v) for v in (True, True, False, True, True, True, True)] == [
        False, False, False, False, False, True, True,
    ]


def hide_legs(pose):
    """Legs out of frame: MediaPipe still returns guessed positions, with near-zero visibility."""
    legs = {SIDES[side][j] for side in SIDES for j in ("hip", "knee", "ankle")}
    return [p._replace(visibility=0.03) if i in legs else p for i, p in enumerate(pose)]


def test_hidden_legs_are_not_counted_or_scored(models):
    driver = Driver(LiveSession(make_plan(("squat", 1, 3)), models))
    for angle in SQUAT_REP:
        result = driver.frame(hide_legs(squat_pose(angle)))
    update = result.update
    assert update.tracking_issue == "body_not_visible"
    assert update.rep_count == 0 and update.form_score is None and update.ml_phase is None
    assert update.landmarks is not None  # still drawn, so the user sees what the camera sees
    # Once the legs are visible again, the same movement counts
    assert driver.squat_reps(1).update.rep_count == 1


def test_no_person_reports_tracking_issue(models):
    assert Driver(LiveSession(make_plan(("squat", 1, 1)), models)).frame(None).update.tracking_issue == "no_person"
