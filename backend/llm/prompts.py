"""Prompt templates for plan generation, set coaching, and post-session analysis."""
import json

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


# Shared JSON shape for any prompt that returns a RehabPlan
PLAN_JSON_SHAPE = """{{
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
}}"""

SET_COACHING_PROMPT = """
You are a physical therapy assistant coaching a rehab patient between sets.

The patient just finished set {set_number} of {total_sets} of {exercise}. Measured data
for each rep (form_score and joint_scores are 0-100, where 100 means every joint angle
was inside its ideal range; fatigue_drift_pct is how far the rep's score fell below the
patient's own baseline; asymmetry_deg is the left/right angle difference):

{rep_data}

Give specific, actionable coaching for the next set based on this data: name the joint
or pattern that needs attention and what to do about it. Do not give generic exercise
tips. If form was consistently good, say so briefly and encourage the same control.
Use at most 3 sentences.

Return a JSON object: {{"coaching": "string"}}
"""

SESSION_ANALYSIS_PROMPT = """
You are a physical therapy assistant reviewing a completed rehab exercise session.

Session data (form scores are 0-100 from joint angle rules; fatigue drift is the drop
from the patient's first-3-rep baseline; asymmetry is left/right angle difference in
degrees; posture_check comes from a classifier and "acceptable_for_rehab_depth" means
the patient used an intentionally partial range of motion):

{session_data}

Analyze which exercises had declining form, where fatigue set in, and which joints
were consistently weakest. Base every finding on the data.

Return a JSON object:
{{
    "summary": "2-3 sentence overview",
    "findings": ["specific finding", ...],
    "weak_joints": ["joint name", ...]
}}
"""

TREND_COMPARISON_PROMPT = """
You are a physical therapy assistant comparing a patient's rehab sessions over time.

This session's analysis:
{current_analysis}

This session's stats:
{current_stats}

Previous sessions, oldest first:
{history}

Identify trends across sessions, for example form improving or fatigue setting in
earlier, quoting the numbers. Recommend one concrete adjustment.

Return a JSON object:
{{
    "summary": "1-2 sentence overview of the trend",
    "trends": ["specific trend with numbers", ...],
    "recommendation": "string"
}}
"""

NEXT_PLAN_PROMPT = """
You are a physical therapy assistant adjusting a rehab plan for the patient's next session.

Patient profile:
- Age: {age}
- Injury: {injury}
- Mobility level: {mobility}
- Pain tolerance: {pain_tolerance}/10

Plan used this session:
{current_plan}

Analysis of this session:
{analysis}

Trend across sessions (may be empty for a first session):
{comparison}

Adjust the plan: add reps if form held up, reduce volume or add rest if fatigue set in
early, and keep exercises appropriate for the injury. Available exercises: squat, push_up.
Make small, safe changes. Keep total session under 20 minutes.

Return a JSON object with this exact structure:
{plan_shape}
"""


def _plan_shape() -> str:
    return PLAN_JSON_SHAPE.format(
        max_sets=settings.MAX_SETS,
        max_reps=settings.MAX_REPS_PER_SET,
        min_rest=settings.MIN_REST_SECONDS,
        max_rest=settings.MAX_REST_SECONDS,
    )


def _json(data) -> str:
    return json.dumps(data, indent=2)


def build_coaching_prompt(payload: dict) -> str:
    return SET_COACHING_PROMPT.format(
        set_number=payload["set_number"],
        total_sets=payload["total_sets"],
        exercise=payload["exercise"].replace("_", "-"),
        rep_data=_json(payload["reps"]),
    )


def build_analysis_prompt(session_data: dict) -> str:
    return SESSION_ANALYSIS_PROMPT.format(session_data=_json(session_data))


def build_comparison_prompt(analysis: dict, current_stats: dict, history: list[dict]) -> str:
    return TREND_COMPARISON_PROMPT.format(
        current_analysis=_json(analysis), current_stats=_json(current_stats), history=_json(history)
    )


def build_next_plan_prompt(profile: UserProfile, current_plan: dict, analysis: dict, comparison: dict | None) -> str:
    return NEXT_PLAN_PROMPT.format(
        age=profile.age,
        injury=profile.injury.replace("_", " "),
        mobility=profile.mobility,
        pain_tolerance=profile.pain_tolerance,
        current_plan=_json(current_plan),
        analysis=_json(analysis),
        comparison=_json(comparison or {}),
        plan_shape=_plan_shape(),
    )
