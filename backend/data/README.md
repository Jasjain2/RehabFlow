# Training data

## Source

**Dataset for: Non-standard Squat Posture Detection Method Using Human Skeleton**
Zenodo, DOI [10.5281/zenodo.18859797](https://doi.org/10.5281/zenodo.18859797), published 2026-03-04, CC BY 4.0.

MediaPipe pose landmarks (33 points: x, y, z, visibility) extracted from video of
subjects performing bodyweight squats. Raw video is not published.

| Folder | Squat type | Form label | Recordings | Subjects |
|---|---|---|---|---|
| `00_Standard` | standard | good | 193 | 17 (p01–p13, p15–p18) |
| `01_Err_Shallow` | shallow | bad | 23 | 4 (p01–p04) |
| `02_Err_GoodMorning` | good_morning | bad | 10 | 1 (p01) |

Each recording is one rep (56–133 frames). 18,302 frames in total, none with missing values.

The dataset description says 22 subjects; the published files contain 17. Incorrect
form was recorded by only 4 subjects, and the good-morning error by only 1.
`02_Err_GoodMorning.zip` also contains byte-identical copies of the other two folders;
`download_squat_data.py` extracts each folder only from its own zip.

## Reproduce

```
python scripts/download_squat_data.py   # downloads, verifies MD5, extracts to raw/squat/
python scripts/process_data.py          # writes processed/
```

`raw/` and `processed/` are not committed.

## Processing

1. Each frame's 33 landmarks go through `tracking/features.py`, the same code the app
   runs on live frames. Features:
   - x, y of every landmark, centered on the hip midpoint and scaled by torso length (66)
   - joint angles: knee, hip, elbow, shoulder, body straightness, trunk lean, knee valgus (7)
   - left/right asymmetry of each angle (7)
2. **Phase labels** come from the knee angle, using the rep counter's thresholds in
   `config/exercises.py`: `standing` at ≥160°, `bottom` at ≤100°. Frames in between are
   `descending` before the recording's deepest frame and `ascending` after it.
   Shallow and good-morning reps rarely or never reach `bottom`, the same way the rep
   counter treats them.
3. **Form labels:** standard → `good`; shallow and good morning → `bad`.
4. `subject_id` (e.g. `p03`) is the group for GroupKFold, so no subject appears in both
   the training and test folds.

## Outputs (`processed/`)

| File | Rows | Contents |
|---|---|---|
| `squat.csv` | 18,302 | ids, squat type, form label, phase label, knee angle, features |
| `phase_training.csv` | 18,302 | ids, `phase_label`, features |
| `form_quality_training.csv` | 12,409 | ids, `form_label`, features; `standing` frames removed, since a standing pose looks the same whatever the squat type |

ID columns: `exercise_label`, `subject_id`, `recording_id`, `frame`, `squat_type`.

## Push-ups

The InfiniteRep push-up videos are not processed yet, so the phase detector is
trained on squats only. Push-up phases come from the rule-based elbow angle thresholds.
