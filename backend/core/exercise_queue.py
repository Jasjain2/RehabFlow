"""Progress through a plan: exercises -> sets -> reps, with rest between sets."""
import math
from dataclasses import dataclass

from core.schema import Exercise, RehabPlan, SessionStatus


@dataclass(frozen=True)
class QueueEvent:
    set_completed: bool = False
    exercise_completed: bool = False
    session_completed: bool = False


class ExerciseQueue:
    def __init__(self, plan: RehabPlan):
        self.plan = plan
        self.exercise_index = 0
        self.set_number = 1
        self.rep_in_set = 0
        self.total_reps = 0
        self.status: SessionStatus = "exercising"
        self._rest_ends_at: float | None = None
        self._advance_exercise_after_rest = False

    @property
    def current(self) -> Exercise:
        return self.plan.exercises[self.exercise_index]

    def record_rep(self, now: float) -> QueueEvent:
        """Count a completed rep. `now` is a monotonic timestamp in seconds."""
        if self.status != "exercising":
            raise RuntimeError(f"Can't record a rep while {self.status}")
        self.rep_in_set += 1
        self.total_reps += 1
        if self.rep_in_set < self.current.reps_per_set:
            return QueueEvent()

        last_set = self.set_number == self.current.sets
        if last_set and self.exercise_index == len(self.plan.exercises) - 1:
            self.status = "complete"
            return QueueEvent(set_completed=True, exercise_completed=True, session_completed=True)

        self.status = "resting"
        self._rest_ends_at = now + self.current.rest_seconds
        self._advance_exercise_after_rest = last_set
        return QueueEvent(set_completed=True, exercise_completed=last_set)

    def tick(self, now: float) -> None:
        """End the rest period once its time is up."""
        if self.status == "resting" and self._rest_ends_at is not None and now >= self._rest_ends_at:
            self._start_next_set()

    def skip_rest(self) -> None:
        if self.status == "resting":
            self._start_next_set()

    def rest_seconds_remaining(self, now: float) -> int | None:
        if self.status != "resting" or self._rest_ends_at is None:
            return None
        return max(0, math.ceil(self._rest_ends_at - now))

    def _start_next_set(self) -> None:
        if self._advance_exercise_after_rest:
            self.exercise_index += 1
            self.set_number = 1
        else:
            self.set_number += 1
        self.rep_in_set = 0
        self.status = "exercising"
        self._rest_ends_at = None
        self._advance_exercise_after_rest = False
