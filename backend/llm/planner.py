"""Plan generation: profile -> prompt -> Groq -> validated RehabPlan, with fallback."""
import logging

import httpx

from core.schema import RehabPlan, UserProfile
from llm.client import LLMError, call_groq
from llm.fallbacks import load_fallback_plan
from llm.prompts import build_plan_prompt

log = logging.getLogger(__name__)


async def generate_plan(profile: UserProfile, *, http_client: httpx.AsyncClient | None = None) -> RehabPlan:
    """Always returns a valid plan: from the LLM if possible, otherwise a fallback."""
    try:
        return await call_groq(
            build_plan_prompt(profile), RehabPlan.model_validate, purpose="plan", http_client=http_client
        )
    except LLMError as e:
        log.warning("Using fallback plan for injury=%s: %s", profile.injury, e)
        return load_fallback_plan(profile.injury)
