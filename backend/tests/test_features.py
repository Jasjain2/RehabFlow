import pytest

from scripts.process_data import derive_phase_labels
from tracking.analyzer import Landmark
from tracking.features import FEATURE_NAMES, extract_features
from tests.test_scoring import _standing_pose


def test_feature_vector_matches_feature_names():
    assert len(extract_features(_standing_pose())) == len(FEATURE_NAMES)


def test_features_invariant_to_position_and_distance():
    pose = _standing_pose()
    # Same pose, shifted in the frame and half the size (user farther from the camera)
    moved = [Landmark(0.2 + 0.5 * p.x, 0.1 + 0.5 * p.y, p.visibility) for p in pose]
    assert extract_features(moved) == pytest.approx(extract_features(pose))


def test_phase_labels_follow_rep_trajectory():
    knee = [175, 165, 150, 120, 95, 80, 90, 130, 155, 170]
    assert derive_phase_labels(knee) == [
        "standing", "standing", "descending", "descending", "bottom",
        "bottom", "bottom", "ascending", "ascending", "standing",
    ]


def test_shallow_rep_never_reaches_bottom():
    assert "bottom" not in derive_phase_labels([175, 150, 120, 110, 125, 150, 172])
