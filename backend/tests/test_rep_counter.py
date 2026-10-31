import math

import pytest

from tracking.rep_counter import RepCounter

FRAMES = 3  # consecutive_frames_for_transition in config


def feed(counter: RepCounter, phases: list[str], frames: int = FRAMES) -> int:
    """Observe each phase for `frames` frames. Returns number of reps completed."""
    completed = 0
    for phase in phases:
        for _ in range(frames):
            completed += counter.observe(phase)
    return completed


def test_full_squat_cycle_counts_one_rep():
    counter = RepCounter("squat")
    assert feed(counter, ["descending", "bottom", "ascending", "standing"]) == 1
    assert counter.rep_count == 1
    assert counter.phase == "standing"


def test_full_pushup_cycle_counts_one_rep():
    counter = RepCounter("push_up")
    assert feed(counter, ["down", "up"]) == 1
    assert counter.rep_count == 1


def test_single_frame_noise_does_not_advance():
    counter = RepCounter("squat")
    counter.observe("descending")
    counter.observe("standing")
    counter.observe("descending")
    counter.observe("descending")
    assert counter.phase == "standing"


def test_three_consecutive_frames_advances():
    counter = RepCounter("squat")
    feed(counter, ["descending"], frames=2)
    assert counter.phase == "standing"
    counter.observe("descending")
    assert counter.phase == "descending"


def test_partial_cycle_does_not_count():
    counter = RepCounter("squat")
    assert feed(counter, ["descending", "standing"]) == 0
    assert counter.rep_count == 0
    # The aborted attempt must not carry over into the next rep
    assert feed(counter, ["descending", "ascending", "standing"]) == 0


def test_consecutive_reps_count_correctly():
    counter = RepCounter("squat")
    cycle = ["descending", "bottom", "ascending", "standing"]
    assert feed(counter, cycle * 2) == 2
    assert counter.rep_count == 2


def test_fast_descent_can_skip_intermediate_phases():
    counter = RepCounter("squat")
    assert feed(counter, ["bottom", "standing"]) == 1


def test_none_observation_is_ignored():
    counter = RepCounter("push_up")
    counter.observe("down")
    counter.observe(None)
    counter.observe("down")
    counter.observe("down")
    assert counter.phase == "down"


def test_unknown_phase_raises():
    with pytest.raises(ValueError):
        RepCounter("push_up").observe("bottom")


def test_squat_counted_from_knee_angles():
    counter = RepCounter("squat")
    angles = [175, 175, 175, 150, 135, 120, 95, 85, 80, 80, 120, 140, 165, 170, 172]
    completed = [counter.update(a) for a in angles]
    assert counter.rep_count == 1
    assert completed.index(True) == len(angles) - 1


def test_shallow_squat_from_angles_does_not_count():
    counter = RepCounter("squat")
    for angle in [175, 150, 130, 115, 110, 110, 125, 145, 165, 170, 172]:
        counter.update(angle)
    assert counter.rep_count == 0


def test_pushup_counted_from_elbow_angles():
    counter = RepCounter("push_up")
    for angle in [170, 160, 130, 95, 90, 88, 120, 155, 165, 170]:
        counter.update(angle)
    assert counter.rep_count == 1


def test_nan_angle_gives_no_evidence():
    counter = RepCounter("push_up")
    for angle in [95, math.nan, 90, 88]:
        counter.update(angle)
    assert counter.phase == "down"
