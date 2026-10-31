"""Post-session analysis: a 3-step LLM chain, each step's output feeding the next.

1. Session analysis: this session's rep data -> findings
2. Trend comparison: findings + previous sessions -> trends (skipped without history)
3. Next-session plan: plan + findings + trends -> adjusted RehabPlan

If step 1 fails, the whole analysis is skipped. If step 2 or 3 fails, that step is
skipped and the earlier output is kept.
"""
import logging
from dataclasses import dataclass

import httpx

from core.schema import RehabPlan, SessionAnalysis, TrendComparison, UserProfile
from llm.client import LLMError, call_groq
from llm.prompts import build_analysis_prompt, build_comparison_prompt, build_next_plan_prompt

log = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    analysis: SessionAnalysis | None = None
    comparison: TrendComparison | None = None
    next_plan: RehabPlan | None = None


async def run_session_analysis(
    session_data: dict,
    current_stats: dict,
    history: list[dict],
    profile: UserProfile,
    plan: RehabPlan,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> AnalysisResult:
    result = AnalysisResult()
    try:
        result.analysis = await call_groq(
            build_analysis_prompt(session_data), SessionAnalysis.model_validate,
            purpose="session analysis", http_client=http_client,
        )
    except LLMError as e:
        log.warning("Session analysis failed, skipping the analysis chain: %s", e)
        return result

    analysis = result.analysis.model_dump()
    if history:
        try:
            result.comparison = await call_groq(
                build_comparison_prompt(analysis, current_stats, history), TrendComparison.model_validate,
                purpose="trend comparison", http_client=http_client,
            )
        except LLMError as e:
            log.warning("Trend comparison failed, continuing without it: %s", e)

    try:
        result.next_plan = await call_groq(
            build_next_plan_prompt(
                profile, plan.model_dump(), analysis, result.comparison.model_dump() if result.comparison else None
            ),
            RehabPlan.model_validate, purpose="next plan", http_client=http_client,
        )
    except LLMError as e:
        log.warning("Next-session plan failed, continuing without it: %s", e)
    return result
