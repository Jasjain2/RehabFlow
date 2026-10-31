"""Prompt templates for plan generation."""
from config import settings
from core.schema import UserProfile

DIFFICULTY_GUIDANCE = {
    "conservative": (
        "Conservative: use the low end of the volume range, at least 90 seconds of rest, "
        "a reduced range of motion, and extra safety warnings."
    ),
    "moderate": "Moderate: balanced volume and rest appropriate for the injury.",
    "aggressive": (
        "Aggressive: higher volume and shorter rest, while staying within what is safe "
        "for the injury and pain tolerance."
    ),
}

PLAN_GENERATION_PROMPT = """
You are a physical therapy assistant. Generate a rehabilitation exercise plan.

Patient profile:
- Age: {age}
- Injury: {injury}
- Mobility level: {mobility}
- Pain tolerance: {pain_tolerance}/10
- Difficulty: {difficulty_guidance}

Available exercises: squat, push_up

Return a JSON object with this exact structure:
{{
    "exercises": [
        {{
            "name": "squat" or "push_up",
            "sets": integer between 1 and {max_sets},
            "reps_per_set": integer between 1 and {max_reps},
            "rest_seconds": integer between {min_rest} and {max_rest},
            "coaching_cues": ["string"],
            "safety_warnings": ["string"]
        }}
    ],
    "warmup": "string",
    "cooldown": "string",
    "overall_safety": "string"
}}

Consider the patient's injury and mobility when choosing exercises and volume.
A patient with knee injury should focus on squats with low volume.
A patient with shoulder/upper body injury should focus on push-ups.
Lower pain tolerance means lower volume and more rest.
Keep total session under 20 minutes.
"""


def build_plan_prompt(profile: UserProfile) -> str:
    return PLAN_GENERATION_PROMPT.format(
        age=profile.age,
        injury=profile.injury.replace("_", " "),
        mobility=profile.mobility,
        pain_tolerance=profile.pain_tolerance,
        difficulty_guidance=DIFFICULTY_GUIDANCE[profile.difficulty],
        max_sets=settings.MAX_SETS,
        max_reps=settings.MAX_REPS_PER_SET,
        min_rest=settings.MIN_REST_SECONDS,
        max_rest=settings.MAX_REST_SECONDS,
    )
