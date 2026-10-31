"""Global thresholds and limits. Exercise-specific values live in config/exercises.py."""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR.parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(BACKEND_DIR / 'rehabflow.db').as_posix()}")

# LLM plan generation
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
# Groq retires models; override with GROQ_MODEL in .env (list: GET /openai/v1/models)
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
# Low for consistent plans, but not 0 so similar profiles don't get identical plans
GROQ_TEMPERATURE = 0.3
GROQ_MAX_TOKENS = 2048
GROQ_TIMEOUT_SECONDS = 30
GROQ_MAX_RETRIES = 3
# Wait 1s, then 2s, between attempts
GROQ_BACKOFF_BASE_SECONDS = 1.0

# Form scoring
POINTS_LOST_PER_DEGREE = 2.0
# Below this MediaPipe visibility a side is treated as occluded and the other side is used
VISIBILITY_THRESHOLD = 0.5

# Rep counting: frame-to-frame change smaller than this is treated as "not moving"
ANGLE_DIRECTION_DEADBAND_DEG = 2.0

# Fatigue detection
FATIGUE_BASELINE_REPS = 3
FATIGUE_MODERATE_DRIFT = 0.15
FATIGUE_HIGH_DRIFT = 0.30

# Models
MODELS_DIR = BACKEND_DIR / "models"
POSE_MODEL_PATH = MODELS_DIR / "pose_landmarker_lite.task"

# Live ML signals. Rules always win for scoring and rep counting.
# A rep the ML model calls "bad" but the rules score above this is shown as acceptable:
# the training data labels any partial-depth squat as bad, which is wrong for rehab.
ML_FORM_OVERRIDE_SCORE = 80
ASYMMETRY_THRESHOLD_DEG = 10.0
# Asymmetry and anomaly flags must persist this many consecutive frames before being
# shown; the anomaly detector flags ~10% of normal frames from unseen subjects.
SIGNAL_CONSECUTIVE_FRAMES = 3

# Gamification
XP_PER_REP = 10
XP_GOOD_FORM_BONUS = 50
XP_GOOD_FORM_THRESHOLD = 80
XP_PLAN_COMPLETE_BONUS = 100
BADGE_FORM_MASTER_SCORE = 90

# Post-session analysis: how many previous sessions to compare against
ANALYSIS_HISTORY_SESSIONS = 5

FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",")

# Profile validation
MIN_AGE = 10
MAX_AGE = 100
MIN_PAIN_TOLERANCE = 1
MAX_PAIN_TOLERANCE = 10

# Plan validation (guards against implausible LLM output)
MAX_SETS = 5
MAX_REPS_PER_SET = 25
MIN_REST_SECONDS = 10
MAX_REST_SECONDS = 300
