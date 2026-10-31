"""Joint angle computation from MediaPipe landmarks and rule-based form scoring."""
import math
from dataclasses import dataclass
from typing import NamedTuple, Sequence

from config.exercises import get_exercise
from config.settings import POINTS_LOST_PER_DEGREE, VISIBILITY_THRESHOLD

NUM_LANDMARKS = 33


class Landmark(NamedTuple):
    """Normalized image coordinates (y grows downward), as produced by MediaPipe."""

    x: float
    y: float
    visibility: float = 1.0


# MediaPipe BlazePose landmark indices
SIDES = {
    "left": {"shoulder": 11, "elbow": 13, "wrist": 15, "hip": 23, "knee": 25, "ankle": 27},
    "right": {"shoulder": 12, "elbow": 14, "wrist": 16, "hip": 24, "knee": 26, "ankle": 28},
}

# Three-point joint angles: (first point, vertex, last point)
JOINT_ANGLES = {
    "knee_flexion": ("hip", "knee", "ankle"),
    "hip_flexion": ("shoulder", "hip", "knee"),
    "elbow_flexion": ("shoulder", "elbow", "wrist"),
    "shoulder_flexion": ("hip", "shoulder", "elbow"),
    "body_straightness": ("ankle", "hip", "shoulder"),
}

# Points each angle depends on, used to judge which side of the body is visible
ANGLE_POINTS = {
    **JOINT_ANGLES,
    "trunk_lean": ("shoulder", "hip"),
    "knee_valgus": ("hip", "knee", "ankle"),
}


@dataclass(frozen=True)
class FrameScore:
    score: float
    joint_scores: dict[str, float]
    # Signed degrees outside the ideal range: negative = below, positive = above, 0 = inside
    deviations: dict[str, float]


def calculate_angle(a: Landmark, b: Landmark, c: Landmark) -> float:
    """Angle at vertex b in degrees (0-180). NaN if either segment has zero length."""
    v1 = (a.x - b.x, a.y - b.y)
    v2 = (c.x - b.x, c.y - b.y)
    n1, n2 = math.hypot(*v1), math.hypot(*v2)
    if n1 == 0 or n2 == 0:
        return math.nan
    cos = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    return math.degrees(math.acos(max(-1.0, min(1.0, cos))))


def trunk_lean(shoulder: Landmark, hip: Landmark) -> float:
    """Degrees the hip-to-shoulder line leans away from vertical (0 = upright)."""
    dx = shoulder.x - hip.x
    dy = hip.y - shoulder.y
    if dx == 0 and dy == 0:
        return math.nan
    return math.degrees(math.atan2(abs(dx), dy))


def knee_valgus(hip: Landmark, knee: Landmark, ankle: Landmark, midline_x: float) -> float:
    """Degrees the knee drifts toward the body midline off the hip-ankle line (frontal view).

    Positive = valgus (knee caving in), negative = varus.
    """
    thigh = math.hypot(knee.x - hip.x, knee.y - hip.y)
    if ankle.y == hip.y or thigh == 0:
        return math.nan
    t = (knee.y - hip.y) / (ankle.y - hip.y)
    line_x = hip.x + t * (ankle.x - hip.x)
    medial = 1.0 if midline_x >= line_x else -1.0
    return math.degrees(math.atan2((knee.x - line_x) * medial, thigh))


def _side_angles(landmarks: Sequence[Landmark], side: str, midline_x: float) -> dict[str, float]:
    pts = {name: landmarks[i] for name, i in SIDES[side].items()}
    angles = {name: calculate_angle(pts[a], pts[b], pts[c]) for name, (a, b, c) in JOINT_ANGLES.items()}
    angles["trunk_lean"] = trunk_lean(pts["shoulder"], pts["hip"])
    angles["knee_valgus"] = knee_valgus(pts["hip"], pts["knee"], pts["ankle"], midline_x)
    return angles


def _combine(left: float, right: float, left_vis: float, right_vis: float) -> float:
    """Average both sides when both are visible, otherwise trust the more visible side."""
    if left_vis >= VISIBILITY_THRESHOLD and right_vis >= VISIBILITY_THRESHOLD:
        values = [v for v in (left, right) if not math.isnan(v)]
        return sum(values) / len(values) if values else math.nan
    return left if left_vis >= right_vis else right


def compute_angles(landmarks: Sequence[Landmark]) -> dict[str, float]:
    """All joint angles for one frame, plus an `<angle>_asymmetry` (|left - right|) for each."""
    if len(landmarks) != NUM_LANDMARKS:
        raise ValueError(f"Expected {NUM_LANDMARKS} landmarks, got {len(landmarks)}")

    midline_x = (landmarks[SIDES["left"]["hip"]].x + landmarks[SIDES["right"]["hip"]].x) / 2
    left = _side_angles(landmarks, "left", midline_x)
    right = _side_angles(landmarks, "right", midline_x)

    angles = {}
    for name, points in ANGLE_POINTS.items():
        left_vis = min(landmarks[SIDES["left"][p]].visibility for p in points)
        right_vis = min(landmarks[SIDES["right"][p]].visibility for p in points)
        angles[name] = _combine(left[name], right[name], left_vis, right_vis)
        angles[f"{name}_asymmetry"] = abs(left[name] - right[name])
    return angles


def score_joint(angle: float, ideal_range: Sequence[float]) -> tuple[float, float]:
    """Return (score, signed deviation). 100 inside the range, minus 2 points per degree outside."""
    low, high = ideal_range
    if angle < low:
        deviation = angle - low
    elif angle > high:
        deviation = angle - high
    else:
        deviation = 0.0
    return max(0.0, 100.0 - POINTS_LOST_PER_DEGREE * abs(deviation)), deviation


def score_frame(exercise: str, phase: str, angles: dict[str, float]) -> FrameScore | None:
    """Score one frame against the ideal ranges for this exercise and phase.

    Only tracked joints that have an ideal range in this phase and a valid angle are
    scored. Returns None if no joint could be scored (e.g. every landmark occluded).
    """
    config = get_exercise(exercise)
    if phase not in config["ideal_ranges"]:
        raise ValueError(f"Unknown phase {phase!r} for {exercise}. Available: {config['phases']}")
    ranges = config["ideal_ranges"][phase]

    joint_scores, deviations = {}, {}
    for joint in config["joints_tracked"]:
        angle = angles.get(joint, math.nan)
        if joint not in ranges or math.isnan(angle):
            continue
        joint_scores[joint], deviations[joint] = score_joint(angle, ranges[joint])

    if not joint_scores:
        return None
    return FrameScore(
        score=sum(joint_scores.values()) / len(joint_scores),
        joint_scores=joint_scores,
        deviations=deviations,
    )
