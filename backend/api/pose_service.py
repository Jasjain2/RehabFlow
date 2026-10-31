"""Process-wide singletons for the MediaPipe pose estimator and the trained ML models."""
import logging
from functools import lru_cache

from config.settings import MODELS_DIR, POSE_MODEL_PATH
from tracking.ml import MLModels
from tracking.pose import PoseEstimator

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_pose_estimator() -> PoseEstimator:
    return PoseEstimator(POSE_MODEL_PATH)


@lru_cache(maxsize=1)
def get_ml_models() -> MLModels | None:
    """None if the model files are missing: the app then runs on rules alone."""
    try:
        return MLModels(MODELS_DIR)
    except FileNotFoundError as e:
        log.warning("ML models not loaded, running rule-based only: %s", e)
        return None
