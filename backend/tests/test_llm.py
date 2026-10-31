import asyncio
import json
from typing import get_args

import httpx
import pytest
from pydantic import ValidationError

from config import settings
from core.schema import InjuryType, RehabPlan, UserProfile
from llm.client import LLMError, call_groq
from llm.fallbacks import DEFAULT_FALLBACK, FALLBACK_DIR, FALLBACK_FILES, load_fallback_plan
from llm.planner import generate_plan
from llm.prompts import build_plan_prompt

VALID_PLAN = {
    "exercises": [{
        "name": "squat", "sets": 2, "reps_per_set": 8, "rest_seconds": 60,
        "coaching_cues": ["Push hips back"], "safety_warnings": ["Stop if knee hurts"],
    }],
    "warmup": "March in place",
    "cooldown": "Stretch quads",
    "overall_safety": "Go slow",
}
PROFILE = UserProfile(age=45, injury="upper_body", mobility="limited", pain_tolerance=3)


def groq_response(content: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json={"choices": [{"message": {"content": content}}]})


class FakeGroq:
    """Serves queued responses and records requests."""

    def __init__(self, *responses: httpx.Response):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []
        self.client = httpx.AsyncClient(transport=httpx.MockTransport(self._handle))

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responses.pop(0)


@pytest.fixture
def sleeps(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key")
    recorded = []

    async def fake_sleep(seconds):
        recorded.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    return recorded


def test_valid_plan_passes_pydantic():
    plan = RehabPlan.model_validate(VALID_PLAN)
    assert plan.exercises[0].reps_per_set == 8


def test_malformed_json_raises_validation_error():
    with pytest.raises(ValidationError):
        RehabPlan.model_validate({"exercises": [{"name": "squat"}], "warmup": "w"})
    with pytest.raises(ValidationError):
        RehabPlan.model_validate_json('{"exercises": [')


@pytest.mark.parametrize("path", sorted(FALLBACK_DIR.glob("*.json")), ids=lambda p: p.name)
def test_fallback_plan_matches_schema(path):
    RehabPlan.model_validate_json(path.read_text(encoding="utf-8"))


def test_fallback_exists_for_each_injury_type():
    assert set(FALLBACK_FILES) == set(get_args(InjuryType))
    for injury in get_args(InjuryType):
        assert (FALLBACK_DIR / FALLBACK_FILES[injury]).exists()
        assert load_fallback_plan(injury).exercises
    assert (FALLBACK_DIR / DEFAULT_FALLBACK).exists()


def test_injury_specific_fallbacks_pick_the_right_exercise():
    assert {e.name for e in load_fallback_plan("knee").exercises} == {"squat"}
    assert {e.name for e in load_fallback_plan("shoulder").exercises} == {"push_up"}


def test_prompt_includes_profile_and_difficulty():
    prompt = build_plan_prompt(PROFILE)
    assert "Age: 45" in prompt
    assert "Injury: upper body" in prompt
    assert "Pain tolerance: 3/10" in prompt
    assert "Conservative" in prompt
    assert "Aggressive" in build_plan_prompt(PROFILE.model_copy(update={"difficulty": "aggressive"}))


def test_request_uses_json_mode_and_settings(sleeps):
    groq = FakeGroq(groq_response(json.dumps(VALID_PLAN)))
    asyncio.run(call_groq("prompt", RehabPlan.model_validate, http_client=groq.client))
    body = json.loads(groq.requests[0].content)
    assert body["response_format"] == {"type": "json_object"}
    assert body["model"] == "llama-3.3-70b-versatile"
    assert body["temperature"] == 0.3
    assert groq.requests[0].headers["Authorization"] == "Bearer test-key"


def test_invalid_response_is_retried_with_backoff(sleeps):
    groq = FakeGroq(
        groq_response("not json"),
        groq_response(json.dumps({"exercises": []})),  # fails Pydantic validation
        groq_response(json.dumps(VALID_PLAN)),
    )
    plan = asyncio.run(call_groq("prompt", RehabPlan.model_validate, http_client=groq.client))
    assert plan == RehabPlan.model_validate(VALID_PLAN)
    assert len(groq.requests) == 3
    assert sleeps == [1.0, 2.0]


def test_rate_limit_and_server_errors_are_retried(sleeps):
    groq = FakeGroq(httpx.Response(429), httpx.Response(503), groq_response(json.dumps(VALID_PLAN)))
    asyncio.run(call_groq("prompt", RehabPlan.model_validate, http_client=groq.client))
    assert len(groq.requests) == 3


def test_auth_error_fails_fast(sleeps):
    groq = FakeGroq(httpx.Response(401, json={"error": "invalid key"}))
    with pytest.raises(LLMError, match="401"):
        asyncio.run(call_groq("prompt", RehabPlan.model_validate, http_client=groq.client))
    assert len(groq.requests) == 1
    assert sleeps == []


def test_generate_plan_falls_back_after_all_retries_fail(sleeps):
    groq = FakeGroq(*[groq_response("not json")] * 3)
    plan = asyncio.run(generate_plan(PROFILE, http_client=groq.client))
    assert plan == load_fallback_plan("upper_body")
    assert len(groq.requests) == 3
    assert sleeps == [1.0, 2.0]  # no pointless wait after the final attempt


def test_generate_plan_returns_llm_plan_on_success(sleeps):
    groq = FakeGroq(groq_response(json.dumps(VALID_PLAN)))
    assert asyncio.run(generate_plan(PROFILE, http_client=groq.client)) == RehabPlan.model_validate(VALID_PLAN)


def test_missing_api_key_uses_fallback_without_calling_groq(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")
    groq = FakeGroq()
    plan = asyncio.run(generate_plan(PROFILE, http_client=groq.client))
    assert plan == load_fallback_plan("upper_body")
    assert groq.requests == []
