"""Pydantic models: the single source of truth for data shapes.

frontend/lib/types.ts mirrors these models.
"""
from typing import Literal

from pydantic import BaseModel, Field

from config import settings

InjuryType = Literal["knee", "shoulder", "upper_body", "lower_body", "general"]
MobilityLevel = Literal["limited", "moderate", "full"]
Difficulty = Literal["conservative", "moderate", "aggressive"]
ExerciseName = Literal["squat", "push_up"]
FatigueLevel = Literal["building_baseline", "normal", "moderate", "high"]
FormQuality = Literal["good", "bad"]


class UserProfile(BaseModel):
    age: int = Field(ge=settings.MIN_AGE, le=settings.MAX_AGE)
    injury: InjuryType
    mobility: MobilityLevel
    pain_tolerance: int = Field(ge=settings.MIN_PAIN_TOLERANCE, le=settings.MAX_PAIN_TOLERANCE)
    # New rehab users start easy
    difficulty: Difficulty = "conservative"


class Exercise(BaseModel):
    name: ExerciseName
    sets: int = Field(ge=1, le=settings.MAX_SETS)
    reps_per_set: int = Field(ge=1, le=settings.MAX_REPS_PER_SET)
    rest_seconds: int = Field(ge=settings.MIN_REST_SECONDS, le=settings.MAX_REST_SECONDS)
    coaching_cues: list[str]
    safety_warnings: list[str]


class RehabPlan(BaseModel):
    exercises: list[Exercise] = Field(min_length=1)
    warmup: str
    cooldown: str
    overall_safety: str


SessionStatus = Literal["exercising", "resting", "complete"]


class FrameMessage(BaseModel):
    """Sent by the client over the WebSocket every frame interval."""

    type: Literal["frame"] = "frame"
    image: str  # base64 JPEG, with or without a data: URL prefix


class ExerciseUpdate(BaseModel):
    """Pushed over the WebSocket after each processed frame."""

    status: SessionStatus
    exercise: ExerciseName
    exercise_index: int = Field(ge=0)  # position in plan.exercises
    set_number: int = Field(ge=1)
    total_sets: int = Field(ge=1)
    rep_in_set: int = Field(ge=0)
    reps_per_set: int = Field(ge=1)
    rep_count: int = Field(ge=0)  # total reps completed this session
    phase: str
    # None when no person was detected in the frame
    form_score: float | None = Field(default=None, ge=0, le=100)
    joint_scores: dict[str, float] = {}
    fatigue_level: FatigueLevel
    fatigue_drift: float
    ml_form_quality: FormQuality | None = None
    rest_seconds_remaining: int | None = None
    # 33 [x, y, visibility] triples in normalized image coordinates, for the skeleton overlay
    landmarks: list[tuple[float, float, float]] | None = None


class RepSummary(BaseModel):
    exercise: ExerciseName
    set_number: int = Field(ge=1)
    rep_number: int = Field(ge=1)
    form_score: float = Field(ge=0, le=100)
    fatigue_drift: float
    fatigue_level: FatigueLevel


class SessionReport(BaseModel):
    session_id: str
    total_reps: int = Field(ge=0)
    total_exercises: int = Field(ge=0)
    avg_form_score: float = Field(ge=0, le=100)
    max_fatigue_drift: float
    fatigue_alerts_count: int = Field(ge=0)
    xp_earned: int = Field(ge=0)
    badges: list[str]
    reps: list[RepSummary]
    duration_seconds: int = Field(ge=0)


class HistoryEntry(BaseModel):
    session_id: str
    created_at: str  # ISO 8601
    exercises: list[ExerciseName]
    total_reps: int = Field(ge=0)
    avg_form_score: float = Field(ge=0, le=100)
