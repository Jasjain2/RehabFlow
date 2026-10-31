"""ML feature vector, shared by training (scripts/) and live inference so they can't drift apart."""
import math
from typing import Sequence

from tracking.analyzer import SIDES, Landmark, compute_angles

ANGLE_FEATURES = [
    "knee_flexion",
    "hip_flexion",
    "elbow_flexion",
    "shoulder_flexion",
    "body_straightness",
    "trunk_lean",
    "knee_valgus",
]

FEATURE_NAMES = (
    [f"{axis}_{i}" for i in range(33) for axis in ("nx", "ny")]
    + ANGLE_FEATURES
    + [f"{name}_asymmetry" for name in ANGLE_FEATURES]
)


REP_FEATURE_NAMES = ["knee_min", "hip_min", "trunk_max", "knee_rom"]


def rep_summary_features(frame_angles: Sequence[dict[str, float]]) -> list[float]:
    """Per-rep features for the form quality classifier, in REP_FEATURE_NAMES order.

    `frame_angles` are compute_angles() outputs for every frame of one rep. NaN
    angles (occluded joints) are ignored.
    """
    def valid(name: str) -> list[float]:
        values = [a[name] for a in frame_angles if not math.isnan(a.get(name, math.nan))]
        return values or [math.nan]

    knee = valid("knee_flexion")
    return [min(knee), min(valid("hip_flexion")), max(valid("trunk_lean")), max(knee) - min(knee)]


def normalize_landmarks(landmarks: Sequence[Landmark]) -> list[tuple[float, float]]:
    """Center on the hip midpoint and scale by torso length.

    Raw image coordinates depend on where the user stands and how far they are from
    the camera; normalized ones describe only the body's pose.
    """
    lh, rh = landmarks[SIDES["left"]["hip"]], landmarks[SIDES["right"]["hip"]]
    ls, rs = landmarks[SIDES["left"]["shoulder"]], landmarks[SIDES["right"]["shoulder"]]
    cx, cy = (lh.x + rh.x) / 2, (lh.y + rh.y) / 2
    torso = math.hypot((ls.x + rs.x) / 2 - cx, (ls.y + rs.y) / 2 - cy)
    if torso == 0:
        return [(math.nan, math.nan)] * len(landmarks)
    return [((p.x - cx) / torso, (p.y - cy) / torso) for p in landmarks]


def extract_features(landmarks: Sequence[Landmark]) -> list[float]:
    """Feature vector in FEATURE_NAMES order. May contain NaN for degenerate poses."""
    angles = compute_angles(landmarks)
    coords = [v for xy in normalize_landmarks(landmarks) for v in xy]
    return (
        coords
        + [angles[name] for name in ANGLE_FEATURES]
        + [angles[f"{name}_asymmetry"] for name in ANGLE_FEATURES]
    )
