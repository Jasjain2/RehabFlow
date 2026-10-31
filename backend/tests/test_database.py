import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.database import RepRecord, ReportRecord, SessionRecord, init_db, make_engine


@pytest.fixture
def db():
    engine = make_engine("sqlite://")
    init_db(engine)
    with Session(engine) as session:
        yield session


def make_rep(session_id: str, **overrides) -> RepRecord:
    fields = dict(
        session_id=session_id,
        exercise="squat",
        set_number=1,
        rep_number=1,
        form_score=88.5,
        fatigue_drift=0.0,
        fatigue_level="building_baseline",
        phase_at_completion="standing",
    )
    return RepRecord(**{**fields, **overrides})


def test_session_created_before_profile_gets_uuid(db):
    session = SessionRecord()
    db.add(session)
    db.commit()
    assert len(session.id) == 36
    assert session.created_at is not None
    assert session.disclaimer_acknowledged is False


def test_session_reps_and_report_round_trip(db):
    session = SessionRecord(age=45, injury="knee", mobility="moderate", pain_tolerance=4)
    db.add(session)
    db.commit()
    db.add_all([make_rep(session.id), make_rep(session.id, rep_number=2, ml_form_quality="good")])
    db.add(ReportRecord(session_id=session.id, total_reps=2, total_exercises=1,
                        avg_form_score=88.5, max_fatigue_drift=0.0))
    db.commit()
    db.refresh(session)
    assert [r.rep_number for r in session.reps] == [1, 2]
    assert session.report.total_reps == 2


@pytest.mark.parametrize("overrides", [
    {"form_score": 101},
    {"fatigue_level": "tired"},
    {"ml_form_quality": "ok"},
    {"session_id": "does-not-exist"},
])
def test_rep_constraints_reject_bad_rows(db, overrides):
    session = SessionRecord()
    db.add(session)
    db.commit()
    db.add(make_rep(**{"session_id": session.id, **overrides}))
    with pytest.raises(IntegrityError):
        db.commit()


def test_pain_tolerance_constraint(db):
    db.add(SessionRecord(pain_tolerance=11))
    with pytest.raises(IntegrityError):
        db.commit()
