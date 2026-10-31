import base64
import json
import uuid

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import api.main as main
from api import state
from config import settings
from core.database import make_engine
from core.schema import Exercise, RehabPlan, SessionAnalysis
from llm.analysis import AnalysisResult
from tests.poses import SQUAT_REP, squat_pose

PROFILE = {"age": 45, "injury": "knee", "mobility": "moderate", "pain_tolerance": 4}
TINY_PLAN = RehabPlan(
    exercises=[Exercise(name="squat", sets=1, reps_per_set=2, rest_seconds=30, coaching_cues=[], safety_warnings=[])],
    warmup="w", cooldown="c", overall_safety="s",
)


def jpeg_b64() -> str:
    ok, buffer = cv2.imencode(".jpg", np.zeros((48, 64, 3), dtype=np.uint8))
    return "data:image/jpeg;base64," + base64.b64encode(buffer.tobytes()).decode()


class FakePose:
    """Returns the next synthetic pose for every frame, whatever the image."""

    def __init__(self, poses):
        self.poses = list(poses)

    def detect(self, _rgb):
        return self.poses.pop(0) if self.poses else squat_pose(175)


@pytest.fixture
def client(monkeypatch):
    state.configure(make_engine("sqlite://"))
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")  # LLM calls use fallbacks
    with TestClient(main.app) as c:
        yield c


def new_session(client, user_id="user-1", plan: RehabPlan | None = TINY_PLAN) -> str:
    session_id = client.post("/api/session", json={"user_id": user_id}).json()["session_id"]
    client.post("/api/profile", json={"session_id": session_id, **PROFILE})
    if plan:
        with state.db_session() as db:
            state.save_plan(db, state.get_session(db, session_id), plan)
    return session_id


def stream_reps(client, monkeypatch, session_id: str, reps: int) -> list[dict]:
    monkeypatch.setattr(main, "get_pose_estimator", lambda: FakePose(squat_pose(a) for a in SQUAT_REP * reps))
    frame = json.dumps({"type": "frame", "image": jpeg_b64()})
    with client.websocket_connect(f"/api/exercise/stream?session_id={session_id}") as ws:
        updates = []
        for _ in range(len(SQUAT_REP) * reps):
            ws.send_text(frame)
            updates.append(ws.receive_json())
    return updates


def test_health_endpoint(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["ml_models_loaded"] is True


def test_create_session_returns_uuid(client):
    session_id = client.post("/api/session", json={}).json()["session_id"]
    assert uuid.UUID(session_id).version == 4


def test_save_profile_stores_data(client):
    session_id = client.post("/api/session", json={"user_id": "u"}).json()["session_id"]
    assert client.get(f"/api/session/{session_id}").json()["profile"] is None
    response = client.post("/api/profile", json={"session_id": session_id, **PROFILE, "disclaimer_acknowledged": True})
    assert response.status_code == 200
    details = client.get(f"/api/session/{session_id}").json()
    assert details["profile"] == {**PROFILE, "difficulty": "conservative"}
    assert details["disclaimer_acknowledged"] is True


def test_invalid_profile_rejected(client):
    session_id = client.post("/api/session", json={}).json()["session_id"]
    assert client.post("/api/profile", json={"session_id": session_id, **PROFILE, "age": 5}).status_code == 422


def test_generate_plan_returns_valid_plan(client):
    session_id = new_session(client, plan=None)
    plan = client.post("/api/plan/generate", json={"session_id": session_id}).json()
    RehabPlan.model_validate(plan)
    assert client.get(f"/api/plan/{session_id}").json() == plan


def test_generate_plan_requires_profile(client):
    session_id = client.post("/api/session", json={}).json()["session_id"]
    assert client.post("/api/plan/generate", json={"session_id": session_id}).status_code == 400


def test_unknown_session_is_404(client):
    assert client.get("/api/session/nope").status_code == 404
    assert client.get("/api/plan/nope").status_code == 404
    assert client.get("/api/report/nope").status_code == 404


def test_stream_rejects_unknown_session(client):
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/api/exercise/stream?session_id=nope") as ws:
            ws.receive_json()
    assert exc.value.code == 4404


def test_full_session_flow(client, monkeypatch):
    session_id = new_session(client)
    updates = stream_reps(client, monkeypatch, session_id, reps=2)
    assert updates[-1]["status"] == "complete" and updates[-1]["rep_count"] == 2
    assert any(u["ml_phase_confidence"] is not None for u in updates)
    assert client.get(f"/api/report/{session_id}").status_code == 404  # not finished yet

    report = client.post("/api/exercise/finish", json={"session_id": session_id}).json()
    assert report["total_reps"] == 2 and len(report["reps"]) == 2
    assert report["reps"][0]["ml_form_quality"] in ("good", "bad")
    assert "Plan Complete" in report["badges"] and "First Session" in report["badges"]
    assert report["xp_earned"] >= 2 * settings.XP_PER_REP + settings.XP_PLAN_COMPLETE_BONUS

    # Background analysis has run: no API key, so it is unavailable and the report stands alone
    final = client.get(f"/api/report/{session_id}").json()
    assert final["analysis_status"] == "unavailable" and final["ai_session_analysis"] is None
    # Finishing again returns the same report
    assert client.post("/api/exercise/finish", json={"session_id": session_id}).json()["total_reps"] == 2

    history = client.get("/api/history/user-1").json()
    assert [h["session_id"] for h in history] == [session_id]
    assert history[0]["exercises"] == ["squat"]
    assert client.get("/api/plan/suggested/user-1").status_code == 404


def test_finished_session_stream_is_rejected(client):
    session_id = new_session(client)
    client.post("/api/exercise/finish", json={"session_id": session_id})
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/api/exercise/stream?session_id={session_id}") as ws:
            ws.receive_json()
    assert exc.value.code == 4409


def test_emergency_stop_with_no_reps_gives_empty_report(client):
    session_id = new_session(client)
    report = client.post("/api/exercise/finish", json={"session_id": session_id}).json()
    assert report["total_reps"] == 0 and report["badges"] == [] and report["analysis_status"] == "unavailable"


def test_analysis_produces_suggested_plan_for_next_session(client, monkeypatch):
    next_plan = TINY_PLAN.model_copy(update={"warmup": "adjusted"})

    async def fake_analysis(*_args, **_kwargs):
        return AnalysisResult(analysis=SessionAnalysis(summary="Good session.", findings=["Steady"]), next_plan=next_plan)

    monkeypatch.setattr(main, "run_session_analysis", fake_analysis)
    session_id = new_session(client)
    stream_reps(client, monkeypatch, session_id, reps=1)
    client.post("/api/exercise/finish", json={"session_id": session_id})

    report = client.get(f"/api/report/{session_id}").json()
    assert report["analysis_status"] == "complete"
    assert report["ai_session_analysis"]["summary"] == "Good session."
    assert report["ai_next_plan"]["warmup"] == "adjusted"

    suggestion = client.get("/api/plan/suggested/user-1").json()
    assert suggestion["source_session_id"] == session_id
    new_id = client.post("/api/session/from-suggested", json={"user_id": "user-1"}).json()["session_id"]
    assert client.get(f"/api/plan/{new_id}").json()["warmup"] == "adjusted"
    assert client.get(f"/api/session/{new_id}").json()["profile"]["injury"] == "knee"
