"""Database access for sessions, reps, reports, set coaching, and analysis."""
import json
from datetime import datetime, timezone
from statistics import mean

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from config import settings
from core import report as report_math
from core.database import (
    RepRecord,
    ReportRecord,
    SessionAnalysisRecord,
    SessionRecord,
    SetCoachingRecord,
    init_db,
    make_engine,
    make_session_factory,
)
from core.schema import (
    HistoryEntry,
    RehabPlan,
    RepSummary,
    SessionAnalysis,
    SessionDetails,
    SessionReport,
    SetCoaching,
    SuggestedPlan,
    TrendComparison,
    UserProfile,
)
from llm.analysis import AnalysisResult
from tracking.live_session import CompletedRep

_factory: sessionmaker | None = None


class NotFoundError(LookupError):
    pass


def configure(engine: Engine) -> None:
    global _factory
    init_db(engine)
    _factory = make_session_factory(engine)


def db_session() -> Session:
    if _factory is None:
        configure(make_engine())
    return _factory()


def _utcnow() -> datetime:
    # Naive UTC, matching SQLite's CURRENT_TIMESTAMP
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(dt: datetime) -> str:
    return dt.replace(tzinfo=timezone.utc).isoformat()


# --- Sessions, profiles, plans ---

def get_session(db: Session, session_id: str) -> SessionRecord:
    record = db.get(SessionRecord, session_id)
    if record is None:
        raise NotFoundError(session_id)
    return record


def create_session(db: Session, user_id: str | None) -> SessionRecord:
    record = SessionRecord(user_id=user_id)
    db.add(record)
    db.commit()
    return record


def save_profile(db: Session, record: SessionRecord, profile: UserProfile, disclaimer_acknowledged: bool) -> None:
    record.age = profile.age
    record.injury = profile.injury
    record.mobility = profile.mobility
    record.pain_tolerance = profile.pain_tolerance
    record.difficulty = profile.difficulty
    record.disclaimer_acknowledged = disclaimer_acknowledged
    db.commit()


def profile_of(record: SessionRecord) -> UserProfile | None:
    if record.age is None:
        return None
    return UserProfile(
        age=record.age,
        injury=record.injury,
        mobility=record.mobility,
        pain_tolerance=record.pain_tolerance,
        difficulty=record.difficulty or "conservative",
    )


def save_plan(db: Session, record: SessionRecord, plan: RehabPlan) -> None:
    record.plan_json = plan.model_dump_json()
    db.commit()


def plan_of(record: SessionRecord) -> RehabPlan | None:
    return RehabPlan.model_validate_json(record.plan_json) if record.plan_json else None


def session_details(record: SessionRecord) -> SessionDetails:
    return SessionDetails(
        session_id=record.id,
        user_id=record.user_id,
        created_at=_iso(record.created_at),
        disclaimer_acknowledged=record.disclaimer_acknowledged,
        profile=profile_of(record),
        has_plan=record.plan_json is not None,
        finished=record.finished_at is not None,
    )


def mark_started(db: Session, record: SessionRecord) -> None:
    if record.started_at is None:
        record.started_at = _utcnow()
        db.commit()


# --- Live session data ---

def add_rep(db: Session, session_id: str, rep: CompletedRep) -> None:
    db.add(RepRecord(
        session_id=session_id,
        exercise=rep.exercise,
        set_number=rep.set_number,
        rep_number=rep.rep_number,
        form_score=rep.form_score,
        fatigue_drift=rep.fatigue_drift,
        fatigue_level=rep.fatigue_level,
        phase_at_completion=rep.phase_at_completion,
        joint_scores_json=json.dumps(rep.joint_scores),
        ml_form_quality=rep.ml_form_quality,
        ml_phase_at_completion=rep.ml_phase_at_completion,
        ml_phase_confidence=rep.ml_phase_confidence,
        asymmetry_json=json.dumps(rep.asymmetry),
        anomaly_score=rep.anomaly_score,
        is_anomalous=rep.is_anomalous,
        anomalous_frames=rep.anomalous_frames,
    ))
    db.commit()


def add_set_coaching(db: Session, session_id: str, exercise: str, set_number: int, text: str, rep_data: dict) -> None:
    db.add(SetCoachingRecord(
        session_id=session_id, exercise=exercise, set_number=set_number,
        coaching_text=text, rep_data_json=json.dumps(rep_data),
    ))
    db.commit()


# --- Reports ---

def _finished_sessions(db: Session, user_id: str) -> list[SessionRecord]:
    query = (
        select(SessionRecord)
        .where(SessionRecord.user_id == user_id, SessionRecord.finished_at.is_not(None))
        .order_by(SessionRecord.created_at, SessionRecord.id)
    )
    return list(db.scalars(query))


def finish_session(db: Session, record: SessionRecord) -> bool:
    """Write the report. Returns False if the session was already finished (idempotent)."""
    if record.report is not None:
        return False

    reps = record.reps
    scores = [r.form_score for r in reps]
    avg = mean(scores) if scores else 0.0
    alerts = sum(r.fatigue_level in ("moderate", "high") for r in reps)
    plan = plan_of(record)
    completed = plan is not None and len(reps) >= report_math.planned_reps(plan)
    first = record.user_id is None or not _finished_sessions(db, record.user_id)

    record.finished_at = _utcnow()
    started = record.started_at or record.finished_at
    db.add(ReportRecord(
        session_id=record.id,
        total_reps=len(reps),
        total_exercises=len({r.exercise for r in reps}),
        avg_form_score=round(avg, 2),
        max_fatigue_drift=max([0.0, *(r.fatigue_drift for r in reps)]),
        fatigue_alerts_count=alerts,
        xp_earned=report_math.compute_xp(len(reps), avg, completed),
        badges_json=json.dumps(report_math.earned_badges(len(reps), avg, alerts, completed, first)),
        duration_seconds=int((record.finished_at - started).total_seconds()),
        anomaly_count=sum(r.anomalous_frames for r in reps),
        symmetry_summary_json=json.dumps(report_math.symmetry_summary(_asymmetry(r) for r in reps)),
    ))
    record.analysis_status = "pending" if reps else "unavailable"
    db.commit()
    db.refresh(record)
    return True


def _asymmetry(rep: RepRecord) -> dict[str, float]:
    return json.loads(rep.asymmetry_json) if rep.asymmetry_json else {}


def _rep_summary(rep: RepRecord) -> RepSummary:
    return RepSummary(
        exercise=rep.exercise,
        set_number=rep.set_number,
        rep_number=rep.rep_number,
        form_score=rep.form_score,
        fatigue_drift=rep.fatigue_drift,
        fatigue_level=rep.fatigue_level,
        ml_form_quality=rep.ml_form_quality,
        posture_check=report_math.posture_check(rep.ml_form_quality, rep.form_score),
        asymmetry=_asymmetry(rep),
        is_anomalous=rep.is_anomalous,
    )


def report_of(record: SessionRecord) -> SessionReport:
    report = record.report
    if report is None:
        raise NotFoundError(record.id)
    analysis = record.analysis
    return SessionReport(
        session_id=record.id,
        total_reps=report.total_reps,
        total_exercises=report.total_exercises,
        avg_form_score=report.avg_form_score,
        max_fatigue_drift=report.max_fatigue_drift,
        fatigue_alerts_count=report.fatigue_alerts_count,
        xp_earned=report.xp_earned,
        badges=json.loads(report.badges_json or "[]"),
        reps=[_rep_summary(r) for r in record.reps],
        duration_seconds=report.duration_seconds or 0,
        symmetry_summary=json.loads(report.symmetry_summary_json or "{}"),
        anomaly_count=report.anomaly_count,
        set_coaching=[
            SetCoaching(exercise=c.exercise, set_number=c.set_number, coaching_text=c.coaching_text)
            for c in record.set_coaching
        ],
        analysis_status=record.analysis_status or "unavailable",
        ai_session_analysis=SessionAnalysis.model_validate_json(analysis.analysis_json) if analysis else None,
        ai_trend_comparison=(
            TrendComparison.model_validate_json(analysis.comparison_json)
            if analysis and analysis.comparison_json else None
        ),
        ai_next_plan=(
            RehabPlan.model_validate_json(analysis.next_plan_json) if analysis and analysis.next_plan_json else None
        ),
    )


def history(db: Session, user_id: str) -> list[HistoryEntry]:
    entries = []
    for record in _finished_sessions(db, user_id):
        if record.report is None:
            continue
        exercises = list(dict.fromkeys(r.exercise for r in record.reps))
        entries.append(HistoryEntry(
            session_id=record.id,
            created_at=_iso(record.created_at),
            exercises=exercises,
            total_reps=record.report.total_reps,
            avg_form_score=record.report.avg_form_score,
        ))
    return entries


# --- Post-session analysis ---

def _session_stats(record: SessionRecord) -> dict:
    report = record.report
    per_exercise: dict[str, list[float]] = {}
    for rep in record.reps:
        per_exercise.setdefault(rep.exercise, []).append(rep.form_score)
    return {
        "date": _iso(record.created_at),
        "total_reps": report.total_reps,
        "avg_form_score": report.avg_form_score,
        "avg_form_score_by_exercise": {e: round(mean(s), 1) for e, s in per_exercise.items()},
        "max_fatigue_drift_pct": round(report.max_fatigue_drift * 100, 1),
        "fatigue_alerts": report.fatigue_alerts_count,
    }


def analysis_inputs(db: Session, record: SessionRecord) -> tuple[dict, dict, list[dict]]:
    """(session rep data, session stats, previous sessions) for the analysis chain."""
    exercises: dict[str, list[dict]] = {}
    for rep in record.reps:
        exercises.setdefault(rep.exercise, []).append({
            "set": rep.set_number,
            "rep": rep.rep_number,
            "form_score": rep.form_score,
            "joint_scores": json.loads(rep.joint_scores_json or "{}"),
            "fatigue_drift_pct": round(rep.fatigue_drift * 100, 1),
            "asymmetry_deg": _asymmetry(rep),
            "posture_check": report_math.posture_check(rep.ml_form_quality, rep.form_score),
            "unusual_movement": rep.is_anomalous,
        })
    session_data = {
        "exercises": [{"name": name, "reps": reps} for name, reps in exercises.items()],
        "fatigue_alerts": record.report.fatigue_alerts_count,
        "duration_seconds": record.report.duration_seconds,
    }

    previous = []
    if record.user_id:
        earlier = [s for s in _finished_sessions(db, record.user_id) if s.id != record.id and s.report]
        for session in earlier[-settings.ANALYSIS_HISTORY_SESSIONS:]:
            stats = _session_stats(session)
            if session.analysis:
                stats["analysis_summary"] = SessionAnalysis.model_validate_json(session.analysis.analysis_json).summary
            previous.append(stats)
    return session_data, _session_stats(record), previous


def save_analysis(db: Session, record: SessionRecord, result: AnalysisResult) -> None:
    if result.analysis is None:
        record.analysis_status = "unavailable"
    else:
        db.add(SessionAnalysisRecord(
            session_id=record.id,
            analysis_json=result.analysis.model_dump_json(),
            comparison_json=result.comparison.model_dump_json() if result.comparison else None,
            next_plan_json=result.next_plan.model_dump_json() if result.next_plan else None,
        ))
        record.analysis_status = "complete"
    db.commit()


def suggested_plan(db: Session, user_id: str) -> SuggestedPlan | None:
    """The adjusted plan from the user's most recent finished session, if it produced one."""
    sessions = _finished_sessions(db, user_id)
    if not sessions:
        return None
    latest = sessions[-1]
    if latest.analysis is None or latest.analysis.next_plan_json is None:
        return None
    return SuggestedPlan(
        source_session_id=latest.id,
        created_at=_iso(latest.created_at),
        plan=RehabPlan.model_validate_json(latest.analysis.next_plan_json),
    )


def create_from_suggested(db: Session, user_id: str) -> SessionRecord:
    suggestion = suggested_plan(db, user_id)
    if suggestion is None:
        raise NotFoundError(user_id)
    source = get_session(db, suggestion.source_session_id)
    record = SessionRecord(
        user_id=user_id,
        age=source.age,
        injury=source.injury,
        mobility=source.mobility,
        pain_tolerance=source.pain_tolerance,
        difficulty=source.difficulty,
        disclaimer_acknowledged=source.disclaimer_acknowledged,
        plan_json=suggestion.plan.model_dump_json(),
    )
    db.add(record)
    db.commit()
    return record
