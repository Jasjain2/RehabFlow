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

from config.settings import DATABASE_URL
from core.schema import FatigueLevel

_FATIGUE_LEVELS_SQL = ", ".join(f"'{level}'" for level in get_args(FatigueLevel))


class Base(DeclarativeBase):
    pass


class SessionRecord(Base):
    __tablename__ = "sessions"
    # Profile columns are nullable: a session is created before the profile is saved
    __table_args__ = (
        CheckConstraint("pain_tolerance BETWEEN 1 AND 10", name="ck_sessions_pain_tolerance"),
    )

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    disclaimer_acknowledged: Mapped[bool] = mapped_column(default=False)
    age: Mapped[int | None]
    injury: Mapped[str | None]
    mobility: Mapped[str | None]
    pain_tolerance: Mapped[int | None]
    difficulty: Mapped[str | None]
    plan_json: Mapped[str | None] = mapped_column(Text)

    reps: Mapped[list["RepRecord"]] = relationship(back_populates="session", order_by="RepRecord.id")
    report: Mapped["ReportRecord | None"] = relationship(back_populates="session")


class RepRecord(Base):
    __tablename__ = "reps"
    __table_args__ = (
        CheckConstraint("form_score BETWEEN 0 AND 100", name="ck_reps_form_score"),
        CheckConstraint(f"fatigue_level IN ({_FATIGUE_LEVELS_SQL})", name="ck_reps_fatigue_level"),
        CheckConstraint("ml_form_quality IN ('good', 'bad')", name="ck_reps_ml_form_quality"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"))
    exercise: Mapped[str]
    set_number: Mapped[int]
    rep_number: Mapped[int]
    form_score: Mapped[float]
    fatigue_drift: Mapped[float]
    fatigue_level: Mapped[str]
    phase_at_completion: Mapped[str]
    joint_scores_json: Mapped[str | None] = mapped_column(Text)
    # NULL for exercises without an ML form classifier (push-ups)
    ml_form_quality: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    session: Mapped[SessionRecord] = relationship(back_populates="reps")


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
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    session: Mapped[SessionRecord] = relationship(back_populates="report")


def make_engine(url: str = DATABASE_URL) -> Engine:
    if not url.startswith("sqlite"):
        return create_engine(url)

    engine = create_engine(url, connect_args={"check_same_thread": False})

    # SQLite ignores foreign keys unless enabled on every connection
    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys = ON")

    return engine


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
