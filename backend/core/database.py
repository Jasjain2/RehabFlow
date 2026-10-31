"""SQLAlchemy models and engine. Swap DATABASE_URL to move from SQLite to PostgreSQL."""
import uuid
from datetime import datetime
from typing import get_args

from sqlalchemy import (
    CheckConstraint,
    Engine,
    ForeignKey,
    Text,
    create_engine,
    event,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import StaticPool

from config.settings import DATABASE_URL
from core.schema import AnalysisStatus, FatigueLevel


def _sql_in(literal_type) -> str:
    return ", ".join(f"'{value}'" for value in get_args(literal_type))


class Base(DeclarativeBase):
    pass


class SessionRecord(Base):
    __tablename__ = "sessions"
    # Profile columns are nullable: a session is created before the profile is saved
    __table_args__ = (
        CheckConstraint("pain_tolerance BETWEEN 1 AND 10", name="ck_sessions_pain_tolerance"),
        CheckConstraint(f"analysis_status IN ({_sql_in(AnalysisStatus)})", name="ck_sessions_analysis_status"),
    )

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str | None] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    disclaimer_acknowledged: Mapped[bool] = mapped_column(default=False)
    age: Mapped[int | None]
    injury: Mapped[str | None]
    mobility: Mapped[str | None]
    pain_tolerance: Mapped[int | None]
    difficulty: Mapped[str | None]
    plan_json: Mapped[str | None] = mapped_column(Text)
    # Set when the live stream first connects and when the session is finished
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    analysis_status: Mapped[str | None]

    reps: Mapped[list["RepRecord"]] = relationship(back_populates="session", order_by="RepRecord.id")
    report: Mapped["ReportRecord | None"] = relationship(back_populates="session")
    set_coaching: Mapped[list["SetCoachingRecord"]] = relationship(order_by="SetCoachingRecord.id")
    analysis: Mapped["SessionAnalysisRecord | None"] = relationship()


class RepRecord(Base):
    __tablename__ = "reps"
    __table_args__ = (
        CheckConstraint("form_score BETWEEN 0 AND 100", name="ck_reps_form_score"),
        CheckConstraint(f"fatigue_level IN ({_sql_in(FatigueLevel)})", name="ck_reps_fatigue_level"),
        CheckConstraint("ml_form_quality IN ('good', 'bad')", name="ck_reps_ml_form_quality"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    exercise: Mapped[str]
    set_number: Mapped[int]
    rep_number: Mapped[int]
    form_score: Mapped[float]
    fatigue_drift: Mapped[float]
    fatigue_level: Mapped[str]
    phase_at_completion: Mapped[str]
    joint_scores_json: Mapped[str | None] = mapped_column(Text)
    # ML columns are NULL for exercises without trained models (push-ups)
    ml_form_quality: Mapped[str | None]
    ml_phase_at_completion: Mapped[str | None]
    ml_phase_confidence: Mapped[float | None]
    # Mean left/right difference per joint label during the rep
    asymmetry_json: Mapped[str | None] = mapped_column(Text)
    # Lowest (most anomalous) Isolation Forest score during the rep
    anomaly_score: Mapped[float | None]
    is_anomalous: Mapped[bool] = mapped_column(default=False)
    anomalous_frames: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    session: Mapped[SessionRecord] = relationship(back_populates="reps")


class SetCoachingRecord(Base):
    __tablename__ = "set_coaching"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    exercise: Mapped[str]
    set_number: Mapped[int]
    coaching_text: Mapped[str] = mapped_column(Text)
    rep_data_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ReportRecord(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), unique=True)
    total_reps: Mapped[int]
    total_exercises: Mapped[int]
    avg_form_score: Mapped[float]
    max_fatigue_drift: Mapped[float]
    fatigue_alerts_count: Mapped[int] = mapped_column(default=0)
    xp_earned: Mapped[int] = mapped_column(default=0)
    badges_json: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[int | None]
    anomaly_count: Mapped[int] = mapped_column(default=0)
    symmetry_summary_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    session: Mapped[SessionRecord] = relationship(back_populates="report")


class SessionAnalysisRecord(Base):
    __tablename__ = "session_analysis"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), unique=True)
    analysis_json: Mapped[str] = mapped_column(Text)
    comparison_json: Mapped[str | None] = mapped_column(Text)
    # Suggested plan for the user's next session
    next_plan_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


def make_engine(url: str = DATABASE_URL) -> Engine:
    if not url.startswith("sqlite"):
        return create_engine(url)

    kwargs: dict = {"connect_args": {"check_same_thread": False}}
    if url in ("sqlite://", "sqlite:///:memory:"):
        # One shared connection, or each thread would get its own empty database
        kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **kwargs)

    # SQLite ignores foreign keys unless enabled on every connection
    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys = ON")

    return engine


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)
