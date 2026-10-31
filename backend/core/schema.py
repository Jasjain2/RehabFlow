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
# Rep-level verdict shown to the user, combining the ML classifier with the rule score
PostureCheck = Literal["good", "needs_attention", "acceptable_for_rehab_depth"]
AnalysisStatus = Literal["pending", "complete", "unavailable"]


# --- WebSocket messages ---

class FrameMessage(BaseModel):
    """Sent by the client every frame interval."""

    type: Literal["frame"] = "frame"
    image: str  # base64 JPEG, with or without a data: URL prefix


class SkipRestMessage(BaseModel):
    type: Literal["skip_rest"] = "skip_rest"


class ExerciseUpdate(BaseModel):
    """Pushed to the client after each processed frame."""

    status: SessionStatus
    exercise: ExerciseName
    exercise_index: int = Field(ge=0)  # position in plan.exercises
    set_number: int = Field(ge=1)
    total_sets: int = Field(ge=1)
    rep_in_set: int = Field(ge=0)
    reps_per_set: int = Field(ge=1)
    rep_count: int = Field(ge=0)  # total reps completed this session
    # Rule-based: drives rep counting and scoring
    phase: str
    # None when no person was detected in the frame
    form_score: float | None = Field(default=None, ge=0, le=100)
    joint_scores: dict[str, float] = {}
    fatigue_level: FatigueLevel
    fatigue_drift: float
    # ML signals (squat only; None for push-ups or when a joint is occluded)
    ml_phase: str | None = None
    ml_phase_confidence: float | None = Field(default=None, ge=0, le=1)
    ml_form_quality: FormQuality | None = None  # last completed rep
    posture_check: PostureCheck | None = None  # last completed rep
    anomaly_score: float | None = None
    is_anomalous: bool = False
    # Left/right differences above the threshold, in degrees, by joint label
    asymmetry_detected: bool = False
    asymmetry_details: dict[str, float] = {}
    rest_seconds_remaining: int | None = None
    # LLM coaching for the set just completed, shown during rest (None while it loads)
    set_coaching: str | None = None
    # 33 [x, y, visibility] triples in normalized image coordinates, for the skeleton overlay
    landmarks: list[tuple[float, float, float]] | None = None


# --- REST requests and responses ---

class CreateSessionRequest(BaseModel):
    # Anonymous browser ID that ties sessions together for history (no accounts)
    user_id: str | None = Field(default=None, max_length=64)


class SessionIdRequest(BaseModel):
    session_id: str


class ProfileRequest(UserProfile):
    session_id: str
    disclaimer_acknowledged: bool = False


class SessionCreated(BaseModel):
    session_id: str


class SessionDetails(BaseModel):
    session_id: str
    user_id: str | None
    created_at: str  # ISO 8601
    disclaimer_acknowledged: bool
    profile: UserProfile | None
    has_plan: bool
    finished: bool


class SuggestedPlan(BaseModel):
    source_session_id: str
    created_at: str
    plan: RehabPlan


class FromSuggestedRequest(BaseModel):
    user_id: str = Field(max_length=64)


class RepSummary(BaseModel):
    exercise: ExerciseName
    set_number: int = Field(ge=1)
    rep_number: int = Field(ge=1)
    form_score: float = Field(ge=0, le=100)
    fatigue_drift: float
    fatigue_level: FatigueLevel
    ml_form_quality: FormQuality | None = None
    posture_check: PostureCheck | None = None
    asymmetry: dict[str, float] = {}
    is_anomalous: bool = False


class SetCoaching(BaseModel):
    exercise: ExerciseName
    set_number: int
    coaching_text: str


class SessionAnalysis(BaseModel):
    """Post-session analysis step 1 (LLM output)."""

    summary: str = Field(min_length=1)
    findings: list[str]
    weak_joints: list[str] = []


class TrendComparison(BaseModel):
    """Post-session analysis step 2 (LLM output)."""

    summary: str = Field(min_length=1)
    trends: list[str]
    recommendation: str


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
    # Mean left/right difference per joint label across the session, in degrees
    symmetry_summary: dict[str, float] = {}
    anomaly_count: int = Field(default=0, ge=0)  # frames flagged as unusual movement
    set_coaching: list[SetCoaching] = []
    analysis_status: AnalysisStatus = "unavailable"
    ai_session_analysis: SessionAnalysis | None = None
    ai_trend_comparison: TrendComparison | None = None
    ai_next_plan: RehabPlan | None = None


class HistoryEntry(BaseModel):
    session_id: str
    created_at: str  # ISO 8601
    exercises: list[ExerciseName]
    total_reps: int = Field(ge=0)
    avg_form_score: float = Field(ge=0, le=100)
