"""Per-set coaching: the rep data from a finished set -> 2-3 sentences of advice."""
import logging
import re

import httpx
from pydantic import BaseModel, Field

from llm.client import LLMError, call_groq
from llm.prompts import build_coaching_prompt

log = logging.getLogger(__name__)

FALLBACK_COACHING = "Take your time on the next set. Focus on controlled movement through the full range of motion."
MAX_SENTENCES = 3


class CoachingResponse(BaseModel):
    coaching: str = Field(min_length=1)


def limit_sentences(text: str, max_sentences: int = MAX_SENTENCES) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[:max_sentences])


async def generate_set_coaching(payload: dict, *, http_client: httpx.AsyncClient | None = None) -> str:
    """Always returns coaching text: from the LLM if possible, otherwise safe generic advice."""
    try:
        response = await call_groq(
            build_coaching_prompt(payload), CoachingResponse.model_validate, purpose="set coaching",
            http_client=http_client,
        )
        return limit_sentences(response.coaching)
    except LLMError as e:
        log.warning("Using fallback coaching for %s set %s: %s", payload["exercise"], payload["set_number"], e)
        return FALLBACK_COACHING
