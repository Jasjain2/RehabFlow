"""Exercise definitions: phases, rep-counting thresholds, and ideal joint angle ranges.

All angles are included joint angles in degrees (180 = fully straight), except
trunk_lean (degrees from vertical) and knee_valgus (degrees of medial knee drift).
Adding an exercise means adding an entry here; the scoring engine, rep counter,
and fatigue detector read everything they need from this dict.
"""

EXERCISES = {
    "squat": {
        "phases": ["standing", "descending", "bottom", "ascending"],
        "primary_angle": "knee_flexion",
        "phase_thresholds": {
            "standing": {"knee_flexion_min": 160},
            "bottom": {"knee_flexion_max": 100},
        },
        # A rep starts and ends in rep_start_phase and must pass through rep_depth_phase
        "rep_start_phase": "standing",
        "rep_depth_phase": "bottom",
        # How deep a rep must go to count, by plan difficulty. Overrides the bottom
        # threshold above: partial-depth squats are the intended movement for many
        # knee rehab patients, so conservative plans count shallower reps.
        "depth_threshold_by_difficulty": {"conservative": 120, "moderate": 110, "aggressive": 100},
        # Ideal ranges replaced per difficulty, so a rep deep enough to count also scores
        # as on-target: a conservative patient at 115 degrees shouldn't lose knee points.
        "ideal_range_overrides_by_difficulty": {
            "conservative": {"bottom": {"knee_flexion": [70, 120]}},
            "moderate": {"bottom": {"knee_flexion": [70, 110]}},
            "aggressive": {"bottom": {"knee_flexion": [70, 95]}},
        },
        # Phases between the thresholds, picked by the direction the primary angle is moving
        "moving_phases": {"decreasing": "descending", "increasing": "ascending"},
        "consecutive_frames_for_transition": 2,
        # knee_valgus is computed as a feature but has no ideal range yet: it needs a
        # frontal camera view, while depth scoring needs a side view.
        "joints_tracked": ["knee_flexion", "hip_flexion", "trunk_lean", "knee_valgus"],
        "ideal_ranges": {
            "standing": {
                "knee_flexion": [165, 180],
                "hip_flexion": [165, 180],
                "trunk_lean": [0, 10],
            },
            "descending": {
                "knee_flexion": [90, 160],
                "hip_flexion": [80, 150],
                "trunk_lean": [0, 30],
            },
            "bottom": {
                "knee_flexion": [70, 95],
                "hip_flexion": [60, 90],
                "trunk_lean": [0, 35],
            },
            "ascending": {
                "knee_flexion": [90, 160],
                "hip_flexion": [80, 150],
                "trunk_lean": [0, 30],
            },
        },
        # Left/right angle pairs checked for asymmetry: display label -> angle
        "asymmetry_joints": {"knee": "knee_flexion", "hip": "hip_flexion"},
        # The trained phase detector, form classifier, and anomaly detector cover this exercise
        "ml_models": True,
    },
    "push_up": {
        "phases": ["up", "down"],
        "primary_angle": "elbow_flexion",
        "phase_thresholds": {
            "up": {"elbow_flexion_min": 150},
            "down": {"elbow_flexion_max": 100},
        },
        "rep_start_phase": "up",
        "rep_depth_phase": "down",
        "moving_phases": {},
        "consecutive_frames_for_transition": 2,
        "joints_tracked": ["elbow_flexion", "shoulder_flexion", "body_straightness"],
        "ideal_ranges": {
            "up": {
                "elbow_flexion": [160, 180],
                "shoulder_flexion": [50, 90],
                "body_straightness": [160, 180],
            },
            "down": {
                "elbow_flexion": [80, 100],
                "shoulder_flexion": [30, 60],
                "body_straightness": [160, 180],
            },
        },
        "asymmetry_joints": {"elbow": "elbow_flexion", "shoulder": "shoulder_flexion"},
        # No labeled push-up data yet: scoring and phases are rule-based only
        "ml_models": False,
    },
}


def get_exercise(name: str) -> dict:
    try:
        return EXERCISES[name]
    except KeyError:
        raise ValueError(f"Unknown exercise {name!r}. Available: {sorted(EXERCISES)}") from None
