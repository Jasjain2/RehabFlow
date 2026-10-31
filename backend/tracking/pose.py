"""MediaPipe BlazePose wrapper: image in, 33 landmarks out."""
import base64
import threading
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

from tracking.analyzer import Landmark


def decode_image(data: str) -> np.ndarray:
    """Base64 JPEG/PNG, optionally a data: URL, to an RGB array. Raises ValueError if invalid."""
    if data.startswith("data:"):
        data = data.split(",", 1)[-1]
    buffer = np.frombuffer(base64.b64decode(data, validate=True), dtype=np.uint8)
    bgr = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("Could not decode image")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


class PoseEstimator:
    """Runs in IMAGE mode, which keeps no state between frames, so one instance can
    serve every session. MediaPipe calls are serialized with a lock."""

    def __init__(self, model_path: Path):
        options = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.IMAGE,
            num_poses=1,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)
        self._lock = threading.Lock()

    def detect(self, rgb: np.ndarray) -> list[Landmark] | None:
        """33 landmarks for the most prominent person, or None if nobody is in frame."""
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        with self._lock:
            result = self._landmarker.detect(image)
        if not result.pose_landmarks:
            return None
        return [Landmark(p.x, p.y, p.visibility or 0.0) for p in result.pose_landmarks[0]]
