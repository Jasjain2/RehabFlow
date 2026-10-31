"""Groq chat completions client with JSON mode, retry, and exponential backoff."""
import asyncio
import json
import logging
import time
from typing import Callable, TypeVar

import httpx

from config import settings

log = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

T = TypeVar("T")


class LLMError(Exception):
    """The LLM could not produce a usable response."""


class _RetryableError(Exception):
    pass


# Network failures, rate limits, server errors, malformed JSON, and responses that fail
# validation (pydantic's ValidationError is a ValueError) are all worth another attempt.
RETRYABLE_ERRORS = (_RetryableError, httpx.TransportError, ValueError, KeyError, IndexError)


async def _request_json(client: httpx.AsyncClient, prompt: str) -> dict:
    response = await client.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
        json={
            "model": settings.GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": settings.GROQ_TEMPERATURE,
            "max_tokens": settings.GROQ_MAX_TOKENS,
        },
    )
    if response.status_code == 429 or response.status_code >= 500:
        raise _RetryableError(f"HTTP {response.status_code}")
    if response.is_error:
        # Bad key or bad request: retrying won't help
        raise LLMError(f"Groq rejected the request: HTTP {response.status_code} {response.text[:200]}")

    data = json.loads(response.json()["choices"][0]["message"]["content"])
    if not isinstance(data, dict):
        raise _RetryableError(f"Expected a JSON object, got {type(data).__name__}")
    return data


async def call_groq(
    prompt: str,
    parse: Callable[[dict], T],
    *,
    http_client: httpx.AsyncClient | None = None,
) -> T:
    """Send `prompt` in JSON mode and return `parse(response_json)`.

    Retries up to GROQ_MAX_RETRIES times, including when `parse` raises a validation
    error. Raises LLMError when no attempt succeeds.
    """
    if not settings.GROQ_API_KEY:
        raise LLMError("GROQ_API_KEY is not set")

    client = http_client or httpx.AsyncClient(timeout=settings.GROQ_TIMEOUT_SECONDS)
    try:
        last_error: Exception | None = None
        for attempt in range(1, settings.GROQ_MAX_RETRIES + 1):
            start = time.perf_counter()
            try:
                result = parse(await _request_json(client, prompt))
            except RETRYABLE_ERRORS as e:
                last_error = e
                latency_ms = (time.perf_counter() - start) * 1000
                log.warning("Groq attempt %d/%d failed after %.0fms: %s",
                            attempt, settings.GROQ_MAX_RETRIES, latency_ms, e)
                if attempt < settings.GROQ_MAX_RETRIES:
                    await asyncio.sleep(settings.GROQ_BACKOFF_BASE_SECONDS * 2 ** (attempt - 1))
                continue

            latency_ms = (time.perf_counter() - start) * 1000
            log.info("Groq call succeeded on attempt %d in %.0fms", attempt, latency_ms)
            return result

        raise LLMError(f"All {settings.GROQ_MAX_RETRIES} attempts failed: {last_error}") from last_error
    finally:
        if http_client is None:
            await client.aclose()
