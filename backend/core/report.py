"""Session report math: XP, badges, and summaries. Pure functions over rep data."""
from collections import defaultdict
from collections.abc import Iterable

from config import settings
from core.schema import PostureCheck, RehabPlan


def posture_check(ml_form_quality: str | None, rep_score: float) -> PostureCheck | None:
    """Combine the ML verdict with the rule score. Rules win: a high rule score overrides
    an ML "bad", which mostly reflects the dataset labeling partial depth as bad form."""
    if ml_form_quality is None:
        return None
    if ml_form_quality == "good":
        return "good"
    return "acceptable_for_rehab_depth" if rep_score > settings.ML_FORM_OVERRIDE_SCORE else "needs_attention"


def planned_reps(plan: RehabPlan) -> int:
    return sum(e.sets * e.reps_per_set for e in plan.exercises)


def compute_xp(total_reps: int, avg_form_score: float, plan_completed: bool) -> int:
    xp = total_reps * settings.XP_PER_REP
    if total_reps and avg_form_score >= settings.XP_GOOD_FORM_THRESHOLD:
        xp += settings.XP_GOOD_FORM_BONUS
    if plan_completed:
        xp += settings.XP_PLAN_COMPLETE_BONUS
    return xp


def earned_badges(
    total_reps: int,
    avg_form_score: float,
    fatigue_alerts: int,
    plan_completed: bool,
    first_session: bool,
) -> list[str]:
    badges = []
    if first_session and total_reps:
        badges.append("First Session")
    if plan_completed:
        badges.append("Plan Complete")
    if total_reps and avg_form_score >= settings.BADGE_FORM_MASTER_SCORE:
        badges.append("Form Master")
    # Past the baseline reps without a single fatigue alert
    if total_reps > settings.FATIGUE_BASELINE_REPS and fatigue_alerts == 0:
        badges.append("Steady Pace")
    return badges


def symmetry_summary(per_rep_asymmetry: Iterable[dict[str, float]]) -> dict[str, float]:
    """Mean left/right difference per joint label across reps where it was measured."""
    values: dict[str, list[float]] = defaultdict(list)
    for rep in per_rep_asymmetry:
        for joint, diff in rep.items():
            values[joint].append(diff)
    return {joint: round(sum(v) / len(v), 1) for joint, v in values.items()}
