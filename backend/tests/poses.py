"""Synthetic side-view poses for driving the live pipeline without a camera."""
import math

from tracking.analyzer import SIDES, Landmark

SEGMENT = 0.2  # thigh and shin length, normalized image units
TORSO = 0.3

# Knee angles for one squat rep, sampled every 400ms: standing, descending, bottom,
# ascending, standing. Each phase lasts at least the 3 frames the rep counter needs.
SQUAT_REP = [175, 175, 175, 150, 130, 110, 90, 85, 85, 90, 110, 130, 150, 170, 175, 175]

# Elbow angles for one push-up rep
PUSHUP_REP = [170, 170, 170, 130, 95, 90, 90, 120, 160, 170, 170]


def squat_pose(
    knee_angle: float,
    trunk_lean: float = 10.0,
    right_knee_angle: float | None = None,
    right_visibility: float = 0.95,
) -> list[Landmark]:
    """Person seen from the side with shins vertical, at the given knee angle."""
    landmarks = [Landmark(0.5, 0.15, 0.95)] * 33  # face points near the head
    for side, dx in (("left", 0.01), ("right", -0.01)):
        angle = right_knee_angle if side == "right" and right_knee_angle is not None else knee_angle
        vis = right_visibility if side == "right" else 0.95
        ankle = (0.5 + dx, 0.9)
        knee = (ankle[0], ankle[1] - SEGMENT)
        theta = math.radians(angle)
        hip = (knee[0] + SEGMENT * math.sin(theta), knee[1] + SEGMENT * math.cos(theta))
        lean = math.radians(trunk_lean)
        shoulder = (hip[0] + TORSO * math.sin(lean), hip[1] - TORSO * math.cos(lean))
        elbow = (shoulder[0], shoulder[1] + 0.15)
        wrist = (elbow[0], elbow[1] + 0.15)
        points = {"ankle": ankle, "knee": knee, "hip": hip, "shoulder": shoulder, "elbow": elbow, "wrist": wrist}
        for joint, (x, y) in points.items():
            landmarks[SIDES[side][joint]] = Landmark(x, y, vis)
    return landmarks


def pushup_pose(elbow_angle: float) -> list[Landmark]:
    """Horizontal body with the upper arm vertical and the forearm at the given elbow angle."""
    landmarks = [Landmark(0.2, 0.5, 0.95)] * 33
    for side, dy in (("left", 0.005), ("right", -0.005)):
        shoulder = (0.3, 0.5 + dy)
        elbow = (0.3, shoulder[1] + 0.12)
        theta = math.radians(elbow_angle)
        # forearm direction measured from the upper arm (elbow -> shoulder points up)
        wrist = (elbow[0] + 0.12 * math.sin(theta), elbow[1] - 0.12 * math.cos(theta))
        points = {"shoulder": shoulder, "elbow": elbow, "wrist": wrist,
                  "hip": (0.6, 0.5 + dy), "knee": (0.75, 0.5 + dy), "ankle": (0.9, 0.5 + dy)}
        for joint, (x, y) in points.items():
            landmarks[SIDES[side][joint]] = Landmark(x, y, 0.95)
    return landmarks
