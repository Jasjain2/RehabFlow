"""Live inference with the models trained by scripts/train_models.py.

All three models are trained on squat data only (see config "ml_models"). Every
method returns None when an input is missing (e.g. an occluded joint), so the
caller falls back to rules alone.
"""
import math
from dataclasses import dataclass
from pathlib import Path

import joblib
import pandas as pd

from core.schema import FormQuality
from tracking.features import FEATURE_NAMES, REP_FEATURE_NAMES


@dataclass(frozen=True)
class PhasePrediction:
    phase: str
    confidence: float


@dataclass(frozen=True)
class AnomalyResult:
    # IsolationForest decision function: negative = anomalous, more negative = more unusual
    score: float
    flagged: bool


def _has_nan(values: list[float]) -> bool:
    return any(math.isnan(v) for v in values)


class MLModels:
    def __init__(self, models_dir: Path):
        self._phase = joblib.load(models_dir / "phase_detector_rf.pkl")
        self._form = joblib.load(models_dir / "form_quality_rf.pkl")
        self._anomaly = joblib.load(models_dir / "anomaly_detector_if.pkl")
        # A model trained on different features than live code computes would silently mispredict
        if self._phase["feature_names"] != FEATURE_NAMES or self._form["feature_names"] != REP_FEATURE_NAMES:
            raise RuntimeError("Model feature names don't match tracking/features.py; retrain the models")
        for bundle in (self._phase, self._form, self._anomaly):
            bundle["model"].set_params(n_jobs=1)

    @staticmethod
    def _row(bundle: dict, values: list[float]) -> pd.DataFrame:
        return pd.DataFrame([values], columns=bundle["feature_names"])

    def predict_phase(self, features: list[float]) -> PhasePrediction | None:
        if _has_nan(features):
            return None
        model = self._phase["model"]
        proba = model.predict_proba(self._row(self._phase, features))[0]
        best = int(proba.argmax())
        return PhasePrediction(phase=str(model.classes_[best]), confidence=float(proba[best]))

    def predict_form(self, rep_features: list[float]) -> FormQuality | None:
        if _has_nan(rep_features):
            return None
        return str(self._form["model"].predict(self._row(self._form, rep_features))[0])  # type: ignore[return-value]

    def detect_anomaly(self, angles: dict[str, float]) -> AnomalyResult | None:
        values = [angles.get(name, math.nan) for name in self._anomaly["feature_names"]]
        if _has_nan(values):
            return None
        score = float(self._anomaly["model"].decision_function(self._row(self._anomaly, values))[0])
        return AnomalyResult(score=score, flagged=score < 0)
