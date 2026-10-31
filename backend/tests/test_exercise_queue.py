import pytest

from core.exercise_queue import ExerciseQueue
from core.schema import Exercise, RehabPlan


def plan() -> RehabPlan:
    def ex(name, sets, reps, rest):
        return Exercise(name=name, sets=sets, reps_per_set=reps, rest_seconds=rest, coaching_cues=[], safety_warnings=[])

    return RehabPlan(exercises=[ex("squat", 2, 2, 60), ex("push_up", 1, 1, 30)], warmup="w", cooldown="c",
                     overall_safety="s")


def test_reps_fill_a_set_then_rest():
    q = ExerciseQueue(plan())
    assert not q.record_rep(0).set_completed
    event = q.record_rep(10)
    assert event.set_completed and not event.exercise_completed
    assert q.status == "resting" and q.rest_seconds_remaining(10) == 60
    assert q.rest_seconds_remaining(40.5) == 30


def test_rest_ends_on_time_or_when_skipped():
    q = ExerciseQueue(plan())
    q.record_rep(0)
    q.record_rep(0)
    q.tick(59)
    assert q.status == "resting"
    q.tick(60)
    assert q.status == "exercising" and q.set_number == 2 and q.rep_in_set == 0

    q.record_rep(70)
    q.record_rep(71)
    q.skip_rest()
    assert q.current.name == "push_up" and q.set_number == 1


def test_last_rep_completes_session():
    q = ExerciseQueue(plan())
    for _ in range(2):
        q.record_rep(0)
        q.record_rep(0)
        q.skip_rest()
    event = q.record_rep(0)
    assert event.session_completed and q.status == "complete"
    assert q.total_reps == 5
    with pytest.raises(RuntimeError):
        q.record_rep(0)
