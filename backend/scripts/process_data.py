"""Turn the raw Zenodo squat CSVs into labeled training data.

Outputs (data/processed/):
  squat.csv                  every frame: ids, labels, knee angle, feature vector
  phase_training.csv         phase detector training set
  form_quality_training.csv  form quality training set (frames in motion only)

Run scripts/download_squat_data.py first.
Usage: python scripts/process_data.py
"""
import sys
from pathlib import Path

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from config.exercises import EXERCISES  # noqa: E402
from tracking.analyzer import Landmark, compute_angles  # noqa: E402
from tracking.features import FEATURE_NAMES, extract_features  # noqa: E402

RAW_DIR = BACKEND_DIR / "data" / "raw" / "squat"
OUT_DIR = BACKEND_DIR / "data" / "processed"

# class folder -> (squat type, form label)
CLASSES = {
    "00_Standard": ("standard", "good"),
    "01_Err_Shallow": ("shallow", "bad"),
    "02_Err_GoodMorning": ("good_morning", "bad"),
}

SQUAT = EXERCISES["squat"]
STANDING_MIN = SQUAT["phase_thresholds"]["standing"]["knee_flexion_min"]
BOTTOM_MAX = SQUAT["phase_thresholds"]["bottom"]["knee_flexion_max"]

ID_COLUMNS = ["exercise_label", "subject_id", "recording_id", "frame", "squat_type"]


def derive_phase_labels(knee_angles: list[float]) -> list[str]:
    """Label each frame of a single-rep recording using the same thresholds as the rep counter.

    standing: knee >= 160, bottom: knee <= 100. In between, frames before the deepest
    point are descending and frames after it are ascending. Each recording holds one
    rep, so the global minimum marks the turnaround.
    """
    turnaround = min(range(len(knee_angles)), key=knee_angles.__getitem__)
    labels = []
    for i, angle in enumerate(knee_angles):
        if angle >= STANDING_MIN:
            labels.append("standing")
        elif angle <= BOTTOM_MAX:
            labels.append("bottom")
        else:
            labels.append("descending" if i < turnaround else "ascending")
    return labels


def process_recording(path: Path, squat_type: str, form_label: str) -> pd.DataFrame:
    raw = pd.read_csv(path)
    landmark_rows = [
        [Landmark(r[f"x_{i}"], r[f"y_{i}"], r[f"v_{i}"]) for i in range(33)]
        for r in raw.to_dict("records")
    ]
    knee = [compute_angles(lm)["knee_flexion"] for lm in landmark_rows]
    features = pd.DataFrame([extract_features(lm) for lm in landmark_rows], columns=FEATURE_NAMES)

    meta = pd.DataFrame({
        "exercise_label": "squat",
        "subject_id": path.stem.split("_")[0],
        "recording_id": path.stem,
        "frame": raw["Frame"],
        "squat_type": squat_type,
        "form_label": form_label,
        "phase_label": derive_phase_labels(knee),
        "knee_angle": knee,
    })
    return pd.concat([meta, features], axis=1)


def main() -> None:
    frames = []
    for folder, (squat_type, form_label) in CLASSES.items():
        paths = sorted((RAW_DIR / folder).glob("*.csv"))
        if not paths:
            sys.exit(f"No CSVs in {RAW_DIR / folder}. Run scripts/download_squat_data.py first.")
        frames += [process_recording(p, squat_type, form_label) for p in paths]
    data = pd.concat(frames, ignore_index=True)

    total = len(data)
    data = data.dropna(subset=FEATURE_NAMES)
    dropped_nan = total - len(data)
    before = len(data)
    data = data.drop_duplicates(subset=["recording_id", *FEATURE_NAMES])
    dropped_dupes = before - len(data)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data.to_csv(OUT_DIR / "squat.csv", index=False)

    phase = data[[*ID_COLUMNS, "phase_label", *FEATURE_NAMES]]
    phase.to_csv(OUT_DIR / "phase_training.csv", index=False)

    # Standing frames look the same in every squat type, so they carry no form signal
    form = data.loc[data["phase_label"] != "standing", [*ID_COLUMNS, "form_label", *FEATURE_NAMES]]
    form.to_csv(OUT_DIR / "form_quality_training.csv", index=False)

    print(f"Frames: {total} read, {dropped_nan} dropped (NaN features), {dropped_dupes} dropped (duplicates)")
    print(f"Recordings: {data['recording_id'].nunique()}  Subjects: {data['subject_id'].nunique()}")
    print("\nRecordings per squat type and subject:")
    print(data.groupby(["subject_id", "squat_type"])["recording_id"].nunique().unstack(fill_value=0).to_string())
    print(f"\nphase_training.csv: {len(phase)} frames")
    print(phase["phase_label"].value_counts().to_string())
    print("\nPhase labels by squat type:")
    print(pd.crosstab(data["squat_type"], data["phase_label"]).to_string())
    print(f"\nform_quality_training.csv: {len(form)} frames (standing excluded)")
    print(form["form_label"].value_counts().to_string())


if __name__ == "__main__":
    main()
