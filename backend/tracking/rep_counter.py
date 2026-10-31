"""Rep counting via a debounced phase state machine.

Each frame yields a phase observation, either from the primary joint angle
(`update`) or from the ML phase detector (`observe`). The committed phase only
changes after the same new phase is observed on N consecutive frames, so
single-frame jitter around a threshold can't advance the state.

A rep is counted when the movement returns to the start phase (standing / up)
after having reached the depth phase (bottom / down). Returning to the start
phase without reaching depth is a partial rep and is not counted. Intermediate
phases may be skipped, because at 400ms per frame a fast descent can go
straight from standing to bottom.
"""
import math

from config.exercises import get_exercise
from config.settings import ANGLE_DIRECTION_DEADBAND_DEG


def classify_phase(config: dict, angle: float, previous_angle: float | None) -> str | None:
    """Phase implied by the primary angle, or None if this frame gives no clear evidence."""
    if math.isnan(angle):
        return None
    primary = config["primary_angle"]
    start, depth = config["rep_start_phase"], config["rep_depth_phase"]
    if angle >= config["phase_thresholds"][start][f"{primary}_min"]:
        return start
    if angle <= config["phase_thresholds"][depth][f"{primary}_max"]:
        return depth

    moving = config["moving_phases"]
    if not moving or previous_angle is None:
        return None
    delta = angle - previous_angle
    if abs(delta) < ANGLE_DIRECTION_DEADBAND_DEG:
        return None
    return moving["increasing"] if delta > 0 else moving["decreasing"]


class RepCounter:
    def __init__(self, exercise: str):
        self.config = get_exercise(exercise)
        self.required_frames = self.config["consecutive_frames_for_transition"]
        self.start_phase = self.config["rep_start_phase"]
        self.depth_phase = self.config["rep_depth_phase"]

        self.phase = self.start_phase
        self.rep_count = 0
        self._reached_depth = False
        self._candidate: str | None = None
        self._streak = 0
        self._previous_angle: float | None = None

    def update(self, angle: float) -> bool:
        """Feed the primary joint angle for one frame. Returns True if a rep was just completed."""
        observed = classify_phase(self.config, angle, self._previous_angle)
        if not math.isnan(angle):
            self._previous_angle = angle
        return self.observe(observed)

    def observe(self, observed: str | None) -> bool:
        """Feed one frame's phase observation. Returns True if a rep was just completed."""
        if observed is None:
            return False
        if observed not in self.config["phases"]:
            raise ValueError(f"Unknown phase {observed!r}. Available: {self.config['phases']}")

        if observed == self.phase:
            self._candidate, self._streak = None, 0
            return False
        if observed == self._candidate:
            self._streak += 1
        else:
            self._candidate, self._streak = observed, 1
        if self._streak < self.required_frames:
            return False

        return self._transition(observed)

    def _transition(self, phase: str) -> bool:
        self.phase = phase
        self._candidate, self._streak = None, 0

        if phase == self.depth_phase:
            self._reached_depth = True
        elif phase == self.start_phase:
            completed = self._reached_depth
            self._reached_depth = False
            if completed:
                self.rep_count += 1
                return True
        return False
