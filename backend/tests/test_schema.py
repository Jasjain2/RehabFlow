import pytest
from pydantic import ValidationError

from core.schema import RehabPlan, UserProfile

VALID_PROFILE = {"age": 45, "injury": "knee", "mobility": "moderate", "pain_tolerance": 4}


def test_profile_defaults_to_conservative():
    assert UserProfile(**VALID_PROFILE).difficulty == "conservative"


@pytest.mark.parametrize("overrides", [
    {"age": 9},
    {"age": 101},
    {"pain_tolerance": 0},
    {"pain_tolerance": 11},
    {"injury": "my knee hurts"},
    {"mobility": "great"},
    {"difficulty": "extreme"},
])
def test_profile_rejects_invalid_input(overrides):
    with pytest.raises(ValidationError):
        UserProfile(**{**VALID_PROFILE, **overrides})


def test_plan_requires_known_exercise_and_sane_volume():
    exercise = {"name": "squat", "sets": 2, "reps_per_set": 8, "rest_seconds": 60,
                "coaching_cues": [], "safety_warnings": []}
    plan = {"exercises": [exercise], "warmup": "w", "cooldown": "c", "overall_safety": "s"}
    assert RehabPlan(**plan).exercises[0].name == "squat"

    for bad in ({"name": "lunge"}, {"sets": 0}, {"reps_per_set": 100}, {"rest_seconds": 5}):
        with pytest.raises(ValidationError):
            RehabPlan(**{**plan, "exercises": [{**exercise, **bad}]})
    with pytest.raises(ValidationError):
        RehabPlan(**{**plan, "exercises": []})
