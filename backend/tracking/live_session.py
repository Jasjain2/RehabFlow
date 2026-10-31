"""Per-connection live exercise engine: landmarks in, ExerciseUpdate out.

Rules drive everything the user is scored on (phase, rep counting, form score,
fatigue). The ML models run alongside as supplementary signals and never override
the rules. No I/O here: the API layer handles MediaPipe, persistence, and the LLM.
"""
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from statistics import mean
from typing import Sequence

from config import settings
from config.exercises import get_exercise
from core.exercise_queue import ExerciseQueue
from core.report import posture_check
from core.schema import ExerciseUpdate, FatigueLevel, FormQuality, PostureCheck, RehabPlan
from tracking.analyzer import (
    SIDES,
    Landmark,
    angle_visibility,
    bilateral_differences,
    compute_angles,
    score_frame,
    side_angles,
)
from tracking.fatigue import FatigueDetector
from tracking.features import extract_features, rep_summary_features
from tracking.ml import MLModels, PhasePrediction
from tracking.rep_counter import RepCounter

log = logging.getLogger(__name__)
# Per-frame diagnostics, enabled with FRAME_TRACE=1 (see api/logging_config.py)
frame_log = logging.getLogger("rehabflow.frames")


@dataclass
class CompletedRep:
    exercise: str
    set_number: int
    rep_number: int
    form_score: float
    fatigue_drift: float
    fatigue_level: FatigueLevel
    phase_at_completion: str
    joint_scores: dict[str, float]
    ml_form_quality: FormQuality | None
    posture_check: PostureCheck | None
    ml_phase_at_completion: str | None
    ml_phase_confidence: float | None
    asymmetry: dict[str, float]
    anomaly_score: float | None
    is_anomalous: bool
    anomalous_frames: int


@dataclass
class CompletedSet:
    key: tuple[int, int]  # (exercise_index, set_number)
    exercise: str
    set_number: int
    total_sets: int
    reps: list[CompletedRep]


@dataclass
class FrameResult:
    update: ExerciseUpdate
    completed_rep: CompletedRep | None = None
    # Set when a set ends with rest to follow (the LLM coaching trigger)
    completed_set: CompletedSet | None = None


class Debounce:
    """True only after `frames` consecutive True inputs."""

    def __init__(self, frames: int):
        self.frames = frames
        self._streak = 0

    def update(self, value: bool) -> bool:
        self._streak = self._streak + 1 if value else 0
        return self._streak >= self.frames


@dataclass
class _RepFrames:
    """Everything observed since the previous rep ended."""

    scores: list[float] = field(default_factory=list)
    joint_scores: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    angles: list[dict[str, float]] = field(default_factory=list)
    asymmetry: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    anomaly_scores: list[float] = field(default_factory=list)
    anomalous_frames: int = 0


class LiveSession:
    def __init__(self, plan: RehabPlan, models: MLModels | None):
        self.queue = ExerciseQueue(plan)
        self.models = models
        self.anomalous_frames = 0
        self.phase_disagreements = 0
        self._fatigue = [FatigueDetector() for _ in plan.exercises]
        self._active_set: tuple[int, int] | None = None
        self._counter: RepCounter | None = None
        self._rep = _RepFrames()
        self._set_reps: list[CompletedRep] = []
        self._last_rep: CompletedRep | None = None
        self._asymmetry = Debounce(settings.SIGNAL_CONSECUTIVE_FRAMES)
        self._anomaly = Debounce(settings.SIGNAL_CONSECUTIVE_FRAMES)
        # Coaching for the set that just ended, keyed by (exercise_index, set_number)
        self._coaching: tuple[tuple[int, int], str] | None = None
        self._resting_after: tuple[int, int] | None = None

    def skip_rest(self) -> None:
        self.queue.skip_rest()

    def set_coaching(self, set_key: tuple[int, int], text: str) -> None:
        self._coaching = (set_key, text)

    def process_frame(self, landmarks: Sequence[Landmark] | None, now: float) -> FrameResult:
        self.queue.tick(now)
        if self.queue.status == "exercising":
            self._start_set_if_new()

        exercise = self.queue.current
        config = get_exercise(exercise.name)
        update = self._base_update(now)
        if landmarks is not None:
            update.landmarks = [(p.x, p.y, p.visibility) for p in landmarks]
        if self.queue.status != "exercising":
            return FrameResult(update)
        primary = config["primary_angle"]
        if landmarks is None:
            update.tracking_issue = "no_person"
        elif (visibility := angle_visibility(landmarks, primary)) < settings.MIN_TRACKING_VISIBILITY:
            update.tracking_issue = "body_not_visible"
            frame_log.debug("%s joints not visible (best side %.2f)", primary, visibility)
        if update.tracking_issue:
            frame_log.debug("not tracked: %s", update.tracking_issue)
            return FrameResult(update)

        angles = compute_angles(landmarks)
        rep_done = self._counter.update(angles[primary])
        phase = self._counter.phase
        frame = score_frame(exercise.name, phase, angles)

        ml_phase = anomaly = None
        if config["ml_models"] and self.models:
            ml_phase = self.models.predict_phase(extract_features(landmarks))
            anomaly = self.models.detect_anomaly(angles)
            if ml_phase and ml_phase.phase != phase:
                self.phase_disagreements += 1
                log.debug("Phase disagreement: rules=%s ml=%s (%.2f)", phase, ml_phase.phase, ml_phase.confidence)

        if frame_log.isEnabledFor(logging.DEBUG):
            self._trace(landmarks, angles, primary, ml_phase)

        diffs = bilateral_differences(landmarks, list(config["asymmetry_joints"].values()))
        by_label = {label: diffs[angle] for label, angle in config["asymmetry_joints"].items() if angle in diffs}
        over = {label: round(d, 1) for label, d in by_label.items() if d > settings.ASYMMETRY_THRESHOLD_DEG}
        asymmetry_shown = self._asymmetry.update(bool(over))
        anomaly_shown = self._anomaly.update(bool(anomaly and anomaly.flagged))

        rep = self._rep
        rep.angles.append(angles)
        if frame:
            rep.scores.append(frame.score)
            for joint, score in frame.joint_scores.items():
                rep.joint_scores[joint].append(score)
        for label, d in by_label.items():
            rep.asymmetry[label].append(d)
        if anomaly:
            rep.anomaly_scores.append(anomaly.score)
        if anomaly_shown:
            rep.anomalous_frames += 1
            self.anomalous_frames += 1

        result = FrameResult(update)
        if rep_done:
            result.completed_rep = self._complete_rep(exercise.name, phase, ml_phase)
            event = self.queue.record_rep(now)
            if event.set_completed:
                completed = CompletedSet(self._active_set, exercise.name, self._active_set[1], exercise.sets, self._set_reps)
                self._set_reps = []
                if not event.session_completed:
                    result.completed_set = completed
                    self._resting_after = self._active_set
            update = self._base_update(now)
            result.update = update

        update.phase = phase
        update.form_score = frame.score if frame else None
        update.joint_scores = frame.joint_scores if frame else {}
        update.ml_phase = ml_phase.phase if ml_phase else None
        update.ml_phase_confidence = ml_phase.confidence if ml_phase else None
        update.anomaly_score = anomaly.score if anomaly else None
        update.is_anomalous = anomaly_shown
        update.asymmetry_detected = asymmetry_shown
        update.asymmetry_details = over if asymmetry_shown else {}
        update.landmarks = [(p.x, p.y, p.visibility) for p in landmarks]
        return result

    def _trace(self, landmarks, angles: dict[str, float], primary: str, ml_phase: PhasePrediction | None) -> None:
        left, right = side_angles(landmarks)
        joints = ("hip", "knee", "ankle") if primary == "knee_flexion" else ("shoulder", "elbow", "wrist")
        vis = {side: "/".join(f"{landmarks[SIDES[side][j]].visibility:.2f}" for j in joints) for side in SIDES}
        frame_log.debug(
            "%s=%.0f (L %.0f vis %s | R %.0f vis %s) hip=%.0f trunk=%.0f | obs=%s phase=%s pending=%s | ml=%s",
            primary, angles[primary], left[primary], vis["left"], right[primary], vis["right"],
            angles["hip_flexion"], angles["trunk_lean"], self._counter.last_observation, self._counter.phase,
            self._counter.pending, f"{ml_phase.phase} {ml_phase.confidence:.2f}" if ml_phase else "-",
        )

    def _start_set_if_new(self) -> None:
        key = (self.queue.exercise_index, self.queue.set_number)
        if key == self._active_set:
            return
        self._active_set = key
        # Fresh counter per set: the user may have moved around while resting
        self._counter = RepCounter(self.queue.current.name)
        self._rep = _RepFrames()
        self._resting_after = None

    def _complete_rep(self, exercise: str, phase: str, ml_phase: PhasePrediction | None) -> CompletedRep:
        rep, self._rep = self._rep, _RepFrames()
        score = mean(rep.scores) if rep.scores else 0.0
        fatigue = self._fatigue[self.queue.exercise_index]
        fatigue_level = fatigue.update(score)

        ml_form = None
        if get_exercise(exercise)["ml_models"] and self.models:
            ml_form = self.models.predict_form(rep_summary_features(rep.angles))

        completed = CompletedRep(
            exercise=exercise,
            set_number=self.queue.set_number,
            rep_number=self.queue.rep_in_set + 1,
            form_score=round(score, 2),
            fatigue_drift=fatigue.current_drift,
            fatigue_level=fatigue_level,
            phase_at_completion=phase,
            joint_scores={j: round(mean(s), 2) for j, s in rep.joint_scores.items()},
            ml_form_quality=ml_form,
            posture_check=posture_check(ml_form, score),
            ml_phase_at_completion=ml_phase.phase if ml_phase else None,
            ml_phase_confidence=ml_phase.confidence if ml_phase else None,
            asymmetry={label: round(mean(d), 1) for label, d in rep.asymmetry.items()},
            anomaly_score=min(rep.anomaly_scores) if rep.anomaly_scores else None,
            is_anomalous=rep.anomalous_frames > 0,
            anomalous_frames=rep.anomalous_frames,
        )
        self._set_reps.append(completed)
        self._last_rep = completed
        return completed

    def _base_update(self, now: float) -> ExerciseUpdate:
        q = self.queue
        exercise = q.current
        fatigue = self._fatigue[q.exercise_index]
        last = self._last_rep if self._last_rep and self._last_rep.exercise == exercise.name else None
        coaching = None
        if q.status == "resting" and self._coaching and self._coaching[0] == self._resting_after:
            coaching = self._coaching[1]
        return ExerciseUpdate(
            status=q.status,
            exercise=exercise.name,
            exercise_index=q.exercise_index,
            set_number=q.set_number,
            total_sets=exercise.sets,
            rep_in_set=q.rep_in_set,
            reps_per_set=exercise.reps_per_set,
            rep_count=q.total_reps,
            phase=self._counter.phase if self._counter else get_exercise(exercise.name)["rep_start_phase"],
            fatigue_level=fatigue.level,
            fatigue_drift=fatigue.current_drift,
            ml_form_quality=last.ml_form_quality if last else None,
            posture_check=last.posture_check if last else None,
            rest_seconds_remaining=q.rest_seconds_remaining(now),
            set_coaching=coaching,
        )


def rep_coaching_payload(completed: CompletedSet) -> dict:
    """The set's rep data as given to the coaching LLM and stored with its output."""
    return {
        "exercise": completed.exercise,
        "set_number": completed.set_number,
        "total_sets": completed.total_sets,
        "reps": [
            {
                "rep": r.rep_number,
                "form_score": r.form_score,
                "joint_scores": r.joint_scores,
                "lowest_joint": min(r.joint_scores, key=r.joint_scores.get) if r.joint_scores else None,
                "fatigue_drift_pct": round(r.fatigue_drift * 100, 1),
                "asymmetry_deg": r.asymmetry,
                "posture_check": r.posture_check,
            }
            for r in completed.reps
        ],
        "fatigue_drift_pct": round(completed.reps[-1].fatigue_drift * 100, 1) if completed.reps else 0.0,
    }

