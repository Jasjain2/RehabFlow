import json
import math
from pathlib import Path

import pytest

from config.exercises import EXERCISES
from tracking.rep_counter import RepCounter

FRAMES = EXERCISES["squat"]["consecutive_frames_for_transition"]


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
    assert counter.phase == "standing"
    counter.observe("descending")
    counter.observe("ascending")
    assert counter.phase == "standing"


def test_consecutive_frames_advance():
    counter = RepCounter("squat")
    feed(counter, ["descending"], frames=FRAMES - 1)
    assert counter.phase == "standing"
    counter.observe("descending")
    assert counter.phase == "descending"


def test_one_frame_at_depth_counts_once_moving():
    """At 400ms per frame a normal-speed squat may show only one frame at the bottom."""
    counter = RepCounter("squat")
    feed(counter, ["descending"])
    counter.observe("bottom")
    assert feed(counter, ["ascending", "standing"]) == 1


def test_stray_depth_frame_while_standing_does_not_arm_a_rep():
    counter = RepCounter("squat")
    counter.observe("bottom")
    counter.observe("standing")
    # A later partial squat must not count off that stray frame
    assert feed(counter, ["descending", "standing"]) == 0


@pytest.mark.parametrize("difficulty, expected", [("aggressive", 6), ("moderate", 6), ("conservative", 8)])
def test_real_webcam_session_counts_every_rep_that_reached_depth(difficulty, expected):
    """Knee angles from a real webcam session (None = joints not visible). Its 9 squats
    bottomed at 131, 112, 114, 97, 82, 68, 64, 68 and 63 degrees, some for a single
    frame. Depth lines: aggressive 100, moderate 110, conservative 120."""
    angles = json.loads((Path(__file__).parent / "data" / "webcam_session_knee_angles.json").read_text())
    counter = RepCounter("squat", difficulty)
    for angle in angles:
        if angle is not None:
            counter.update(float(angle))
    assert counter.rep_count == expected


def test_depth_threshold_follows_difficulty_for_squats_only():
    assert [RepCounter("squat", d).depth_max for d in ("conservative", "moderate", "aggressive")] == [120, 110, 100]
    assert RepCounter("squat").depth_max == 100  # no difficulty: the phase threshold
    assert RepCounter("push_up", "conservative").depth_max == 100


def test_conservative_counts_a_partial_squat_that_aggressive_does_not():
    partial = [175, 175, 150, 130, 115, 115, 130, 150, 170, 175]
    for difficulty, expected in (("conservative", 1), ("aggressive", 0)):
        counter = RepCounter("squat", difficulty)
        for angle in partial:
            counter.update(angle)
        assert counter.rep_count == expected, difficulty


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
    angles = [175, 175, 175, 150, 135, 120, 95, 85, 80, 80, 120, 140, 165, 170]
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
