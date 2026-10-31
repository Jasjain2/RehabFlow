"""Pre-written plans used when the LLM is unavailable or keeps returning invalid output."""
from config.settings import BACKEND_DIR
from core.schema import InjuryType, RehabPlan

FALLBACK_DIR = BACKEND_DIR / "fallback_plans"
DEFAULT_FALLBACK = "default.json"

FALLBACK_FILES: dict[InjuryType, str] = {
    "knee": "knee_general.json",
    "shoulder": "shoulder_general.json",
    "upper_body": "upper_body_general.json",
    "lower_body": "lower_body_general.json",
    "general": DEFAULT_FALLBACK,
}


def load_fallback_plan(injury: str) -> RehabPlan:
    filename = FALLBACK_FILES.get(injury, DEFAULT_FALLBACK)
    return RehabPlan.model_validate_json((FALLBACK_DIR / filename).read_text(encoding="utf-8"))
