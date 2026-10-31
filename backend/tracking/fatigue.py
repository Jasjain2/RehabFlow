"""Fatigue detection: drift of each rep's form score from the user's own baseline.

Use one detector per exercise, since squat and push-up scores aren't comparable.
"""
from config.settings import FATIGUE_BASELINE_REPS, FATIGUE_HIGH_DRIFT, FATIGUE_MODERATE_DRIFT
from core.schema import FatigueLevel


class FatigueDetector:
    def __init__(self):
        self.baseline_scores: list[float] = []
        self.baseline: float | None = None
        self.current_drift = 0.0
        self.max_drift = 0.0

    def update(self, rep_score: float) -> FatigueLevel:
        if self.baseline is None:
            self.baseline_scores.append(rep_score)
            if len(self.baseline_scores) == FATIGUE_BASELINE_REPS:
                self.baseline = sum(self.baseline_scores) / FATIGUE_BASELINE_REPS
            return "building_baseline"

        # A zero baseline can't drop further; treat it as no drift. Rounding keeps
        # exact threshold values (e.g. 0.15) from landing just below due to float error.
        drift = (self.baseline - rep_score) / self.baseline if self.baseline > 0 else 0.0
        self.current_drift = round(drift, 9)
        self.max_drift = max(self.max_drift, self.current_drift)
        return self.level

    @property
    def level(self) -> FatigueLevel:
        """Level as of the most recent rep."""
        if self.baseline is None:
            return "building_baseline"
        if self.current_drift >= FATIGUE_HIGH_DRIFT:
            return "high"
        if self.current_drift >= FATIGUE_MODERATE_DRIFT:
            return "moderate"
        return "normal"
