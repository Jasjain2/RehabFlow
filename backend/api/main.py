"""FastAPI app: REST endpoints and the live exercise WebSocket.

Run: uvicorn api.main:app --reload   (from backend/)
"""
import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from api import state
from api.logging_config import configure_logging
from api.pose_service import get_ml_models, get_pose_estimator
from config import settings
from core.schema import (
    CreateSessionRequest,
    FrameMessage,
    FromSuggestedRequest,
    HistoryEntry,
    ProfileRequest,
    RehabPlan,
    SessionCreated,
    SessionDetails,
    SessionIdRequest,
    SessionReport,
    SkipRestMessage,
    SuggestedPlan,
    UserProfile,
)
from llm.analysis import run_session_analysis
from llm.coaching import generate_set_coaching
from llm.planner import generate_plan
from tracking.live_session import CompletedSet, FrameResult, LiveSession, rep_coaching_payload
from tracking.pose import PoseEstimator, decode_image

log = logging.getLogger(__name__)

ClientMessage = TypeAdapter(FrameMessage | SkipRestMessage)


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    state.db_session().close()  # create tables on startup
    yield


app = FastAPI(title="RehabFlow API", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.FRONTEND_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _session_or_404(db: Session, session_id: str):
    try:
        return state.get_session(db, session_id)
    except state.NotFoundError:
        raise HTTPException(404, "Session not found") from None


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "ml_models_loaded": get_ml_models() is not None,
        "llm_configured": bool(settings.GROQ_API_KEY),
        "llm_model": settings.GROQ_MODEL,
    }


@app.post("/api/session")
def create_session(request: CreateSessionRequest) -> SessionCreated:
    with state.db_session() as db:
        record = state.create_session(db, request.user_id)
        log.info("Session %s created", record.id)
        return SessionCreated(session_id=record.id)


@app.get("/api/session/{session_id}")
def get_session(session_id: str) -> SessionDetails:
    with state.db_session() as db:
        return state.session_details(_session_or_404(db, session_id))


@app.post("/api/session/from-suggested")
def create_from_suggested(request: FromSuggestedRequest) -> SessionCreated:
    with state.db_session() as db:
        try:
            record = state.create_from_suggested(db, request.user_id)
        except state.NotFoundError:
            raise HTTPException(404, "No suggested plan for this user") from None
        log.info("Session %s created from suggested plan", record.id)
        return SessionCreated(session_id=record.id)


@app.post("/api/profile")
def save_profile(request: ProfileRequest) -> dict:
    with state.db_session() as db:
        record = _session_or_404(db, request.session_id)
        profile = UserProfile.model_validate(request.model_dump(include=set(UserProfile.model_fields)))
        state.save_profile(db, record, profile, request.disclaimer_acknowledged)
    return {"status": "ok"}


@app.post("/api/plan/generate")
async def generate(request: SessionIdRequest) -> RehabPlan:
    with state.db_session() as db:
        profile = state.profile_of(_session_or_404(db, request.session_id))
    if profile is None:
        raise HTTPException(400, "Save a profile before generating a plan")
    plan = await generate_plan(profile)
    with state.db_session() as db:
        state.save_plan(db, _session_or_404(db, request.session_id), plan)
    return plan


@app.get("/api/plan/suggested/{user_id}")
def get_suggested_plan(user_id: str) -> SuggestedPlan:
    with state.db_session() as db:
        suggestion = state.suggested_plan(db, user_id)
    if suggestion is None:
        raise HTTPException(404, "No suggested plan")
    return suggestion


@app.get("/api/plan/{session_id}")
def get_plan(session_id: str) -> RehabPlan:
    with state.db_session() as db:
        plan = state.plan_of(_session_or_404(db, session_id))
    if plan is None:
        raise HTTPException(404, "No plan for this session")
    return plan


def _process_frame(pose: PoseEstimator, live: LiveSession, image: str) -> FrameResult | None:
    try:
        rgb = decode_image(image)
    except ValueError:
        return None
    return live.process_frame(pose.detect(rgb), time.monotonic())


async def _coach_set(live: LiveSession, session_id: str, completed: CompletedSet) -> None:
    payload = rep_coaching_payload(completed)
    text = await generate_set_coaching(payload)
    live.set_coaching(completed.key, text)
    with state.db_session() as db:
        state.add_set_coaching(db, session_id, completed.exercise, completed.set_number, text, payload)


@app.websocket("/api/exercise/stream")
async def exercise_stream(ws: WebSocket, session_id: str) -> None:
    await ws.accept()
    with state.db_session() as db:
        try:
            record = state.get_session(db, session_id)
        except state.NotFoundError:
            await ws.close(code=4404, reason="Session not found")
            return
        plan = state.plan_of(record)
        if plan is None:
            await ws.close(code=4400, reason="This session has no plan yet")
            return
        if record.finished_at is not None:
            await ws.close(code=4409, reason="This session is already finished")
            return
        state.mark_started(db, record)

    live = LiveSession(plan, get_ml_models())
    pose = get_pose_estimator()
    coaching_tasks: set[asyncio.Task] = set()
    frames = frames_with_pose = 0
    processing_s = 0.0
    log.info("Session %s stream connected", session_id)
    try:
        while True:
            try:
                message = ClientMessage.validate_json(await ws.receive_text())
            except ValidationError:
                continue
            if isinstance(message, SkipRestMessage):
                live.skip_rest()
                continue

            start = time.perf_counter()
            result = await run_in_threadpool(_process_frame, pose, live, message.image)
            processing_s += time.perf_counter() - start
            if result is None:
                continue
            frames += 1
            frames_with_pose += result.update.landmarks is not None
            if result.completed_rep:
                with state.db_session() as db:
                    state.add_rep(db, session_id, result.completed_rep)
                if result.completed_rep.fatigue_level in ("moderate", "high"):
                    log.info("Session %s fatigue %s (drift %.0f%%)", session_id,
                             result.completed_rep.fatigue_level, result.completed_rep.fatigue_drift * 100)
            if result.completed_set:
                task = asyncio.create_task(_coach_set(live, session_id, result.completed_set))
                coaching_tasks.add(task)
                task.add_done_callback(coaching_tasks.discard)
            await ws.send_text(result.update.model_dump_json())
    except WebSocketDisconnect:
        log.info("Session %s stream disconnected: %d frames, %d with a person detected, %.0fms avg processing, "
                 "%d reps, %d ML/rule phase disagreements", session_id, frames, frames_with_pose,
                 processing_s / max(frames, 1) * 1000, live.queue.total_reps, live.phase_disagreements)


async def _analyze_session(session_id: str) -> None:
    with state.db_session() as db:
        record = state.get_session(db, session_id)
        session_data, stats, previous = state.analysis_inputs(db, record)
        profile, plan = state.profile_of(record), state.plan_of(record)
    if profile is None or plan is None:
        result = None
    else:
        result = await run_session_analysis(session_data, stats, previous, profile, plan)
    with state.db_session() as db:
        record = state.get_session(db, session_id)
        if result is None:
            record.analysis_status = "unavailable"
            db.commit()
        else:
            state.save_analysis(db, record, result)
    log.info("Session %s analysis %s", session_id, record.analysis_status)


@app.post("/api/exercise/finish")
def finish(request: SessionIdRequest, background: BackgroundTasks) -> SessionReport:
    """Ends the session and returns its report. The AI analysis runs afterwards in the
    background; poll GET /api/report/{session_id} until analysis_status is no longer pending."""
    with state.db_session() as db:
        record = _session_or_404(db, request.session_id)
        newly_finished = state.finish_session(db, record)
        report = state.report_of(record)
    if newly_finished and report.analysis_status == "pending":
        background.add_task(_analyze_session, request.session_id)
    log.info("Session %s finished: %d reps, avg %.1f", request.session_id, report.total_reps, report.avg_form_score)
    return report


@app.get("/api/report/{session_id}")
def get_report(session_id: str) -> SessionReport:
    with state.db_session() as db:
        record = _session_or_404(db, session_id)
        try:
            return state.report_of(record)
        except state.NotFoundError:
            raise HTTPException(404, "This session hasn't been finished yet") from None


@app.get("/api/history/{user_id}")
def get_history(user_id: str) -> list[HistoryEntry]:
    with state.db_session() as db:
        return state.history(db, user_id)
