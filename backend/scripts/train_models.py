"""Train the phase detector, squat form quality classifier, and anomaly detector.

Prints subject-grouped cross-validation results, then trains each model on all data
and saves it to models/ with its feature names and scores. All scores are also
written to models/model_summary.json.

Then benchmarks Logistic Regression, SVM, Random Forest, and XGBoost on the phase and
form quality tasks, on the same cross-validation splits, and writes
models/model_comparison.json. Random Forest stays the deployed model either way.

Run scripts/process_data.py first.
Usage: python scripts/train_models.py
"""
import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.svm import SVC
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from tracking.features import ANGLE_FEATURES, FEATURE_NAMES, REP_FEATURE_NAMES  # noqa: E402

DATA_DIR = BACKEND_DIR / "data" / "processed"
MODELS_DIR = BACKEND_DIR / "models"
RANDOM_STATE = 42
PHASE_ORDER = ["standing", "descending", "bottom", "ascending"]
ANOMALY_CONTAMINATION = 0.05
# Joint angles only. With landmark coordinates included, the model flagged unfamiliar
# body proportions and camera setups rather than unusual movement: one held-out
# subject had 100% of normal frames flagged (mean 22% vs 10% with angles only).
ANOMALY_FEATURES = ANGLE_FEATURES


def make_forest(**kwargs) -> RandomForestClassifier:
    return RandomForestClassifier(n_estimators=100, random_state=RANDOM_STATE, n_jobs=-1, **kwargs)


def phase_splits(data: pd.DataFrame) -> list:
    return list(GroupKFold(n_splits=5).split(data, groups=data["subject_id"]))


def form_splits(data: pd.DataFrame, y: pd.Series) -> list:
    # Each fold holds out one of the 4 subjects with bad-form data
    return list(StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=RANDOM_STATE)
                .split(data, y, data["subject_id"]))


def single_threaded(model) -> None:
    """Set every n_jobs parameter (including inside pipelines) to 1, as in the live session."""
    model.set_params(**{k: 1 for k in model.get_params() if k == "n_jobs" or k.endswith("__n_jobs")})


def inference_latency_ms(model, X: pd.DataFrame, predict=lambda m, row: m.predict(row), n: int = 200) -> float:
    """Median time to score one sample, as the live session does. Leaves the model single-threaded."""
    single_threaded(model)
    times = []
    for i in range(min(n, len(X))):
        row = X.iloc[[i]]
        start = time.perf_counter()
        predict(model, row)
        times.append((time.perf_counter() - start) * 1000)
    return float(np.median(times))


def save(model, name: str, metrics: dict, feature_names: list[str]) -> None:
    MODELS_DIR.mkdir(exist_ok=True)
    joblib.dump({"model": model, "feature_names": feature_names, "metrics": metrics}, MODELS_DIR / name, compress=3)


def banner(text: str) -> None:
    print("\n" + "=" * 70 + f"\n{text}\n" + "=" * 70)


def train_phase_detector() -> dict:
    data = pd.read_csv(DATA_DIR / "phase_training.csv")
    X, y, groups = data[FEATURE_NAMES], data["phase_label"], data["subject_id"]
    banner(f"PHASE DETECTOR  {len(data)} frames, {groups.nunique()} subjects, GroupKFold(5) by subject")

    fold_scores, oof = [], pd.Series(index=data.index, dtype=object)
    for fold, (train_idx, test_idx) in enumerate(phase_splits(data), 1):
        model = make_forest().fit(X.iloc[train_idx], y.iloc[train_idx])
        pred = model.predict(X.iloc[test_idx])
        oof.iloc[test_idx] = pred
        fold_scores.append(f1_score(y.iloc[test_idx], pred, average="macro"))
        print(f"  fold {fold}: macro F1 {fold_scores[-1]:.4f}  test subjects {sorted(groups.iloc[test_idx].unique())}")

    mean, std = float(np.mean(fold_scores)), float(np.std(fold_scores))
    print(f"\nPhase Detector F1 (macro): {mean:.4f} ± {std:.4f}\n")
    print(classification_report(y, oof, labels=PHASE_ORDER, digits=4))
    print("Confusion matrix (rows = true, cols = predicted):", PHASE_ORDER)
    print(confusion_matrix(y, oof, labels=PHASE_ORDER))

    final = make_forest().fit(X, y)
    latency = inference_latency_ms(final, X)
    print(f"\nSingle-frame inference: {latency:.2f} ms (median)")

    per_class = f1_score(y, oof, labels=PHASE_ORDER, average=None)
    metrics = {
        "f1": round(mean, 4),
        "std": round(std, 4),
        "n_samples": len(data),
        "subjects": int(groups.nunique()),
        "validation": "GroupKFold 5-fold by subject",
        "metric": "macro F1",
        "per_class_f1": {p: round(float(s), 4) for p, s in zip(PHASE_ORDER, per_class)},
        "inference_ms_median": round(latency, 2),
    }
    save(final, "phase_detector_rf.pkl", metrics, FEATURE_NAMES)
    return metrics


def train_form_quality() -> dict:
    data = pd.read_csv(DATA_DIR / "form_quality_rep_training.csv")
    X, groups = data[REP_FEATURE_NAMES], data["subject_id"]
    y = (data["form_label"] == "bad").astype(int)  # positive class = bad form
    bad_subjects = int(data.loc[y == 1, "subject_id"].nunique())
    banner(
        f"FORM QUALITY (squat, rep level)  {len(data)} reps ({y.sum()} bad), {groups.nunique()} subjects, "
        f"{bad_subjects} with bad-form data\nFeatures: {REP_FEATURE_NAMES}\n"
        "StratifiedGroupKFold(4) by subject: each fold holds out one bad-form subject"
    )

    fold_scores = []
    oof = pd.Series(0, index=data.index)
    for fold, (train_idx, test_idx) in enumerate(form_splits(data, y), 1):
        if y.iloc[test_idx].sum() == 0:
            sys.exit(f"Fold {fold} has no bad-form reps; F1 would be undefined")
        model = make_forest(class_weight="balanced").fit(X.iloc[train_idx], y.iloc[train_idx])
        pred = model.predict(X.iloc[test_idx])
        oof.iloc[test_idx] = pred
        fold_scores.append(f1_score(y.iloc[test_idx], pred))
        test = data.iloc[test_idx]
        held_out_bad = sorted(test.loc[y.iloc[test_idx] == 1, "subject_id"].unique())
        print(f"  fold {fold}: F1 {fold_scores[-1]:.4f}  bad-form test subject {held_out_bad}  "
              f"test reps {len(test_idx)} ({int(y.iloc[test_idx].sum())} bad)")

    mean, std = float(np.mean(fold_scores)), float(np.std(fold_scores))
    print(f"\nForm Quality F1 (rep level, bad = positive): {mean:.4f} ± {std:.4f}\n")
    print(classification_report(y, oof, target_names=["good", "bad"], digits=4))
    flagged = {t: round(float(oof[data["squat_type"] == t].mean()), 4) for t in ["shallow", "good_morning", "standard"]}
    print(f"Out-of-fold reps flagged bad: shallow {flagged['shallow']:.4f}, good morning "
          f"{flagged['good_morning']:.4f}, standard (false alarms) {flagged['standard']:.4f}")

    final = make_forest(class_weight="balanced").fit(X, y.map({0: "good", 1: "bad"}))
    latency = inference_latency_ms(final, X)
    print(f"\nSingle-rep inference: {latency:.2f} ms (median)")

    metrics = {
        "f1": round(mean, 4),
        "std": round(std, 4),
        "n_samples": len(data),
        "n_bad": int(y.sum()),
        "subjects": int(groups.nunique()),
        "bad_form_subjects": bad_subjects,
        "validation": "StratifiedGroupKFold 4-fold by subject (one bad-form subject held out per fold)",
        "positive_class": "bad",
        "features": REP_FEATURE_NAMES,
        "fold_f1": [round(float(f), 4) for f in fold_scores],
        "flagged_bad_rate_by_type": flagged,
        "inference_ms_median": round(latency, 2),
    }
    save(final, "form_quality_rf.pkl", metrics, REP_FEATURE_NAMES)
    return metrics


def train_anomaly_detector() -> dict:
    data = pd.read_csv(DATA_DIR / "squat.csv")
    standard = data[data["squat_type"] == "standard"]
    errors = data[data["squat_type"] != "standard"]
    banner(f"ANOMALY DETECTOR (Isolation Forest)  {len(standard)} standard-squat frames, "
           f"{standard['subject_id'].nunique()} subjects, contamination={ANOMALY_CONTAMINATION}")

    def make_iforest() -> IsolationForest:
        return IsolationForest(n_estimators=100, contamination=ANOMALY_CONTAMINATION,
                               random_state=RANDOM_STATE, n_jobs=-1)

    # Unsupervised, so there is no F1. Instead: how often it flags standard frames from
    # subjects it never saw (should stay near the contamination rate).
    held_out_rates = []
    for train_idx, test_idx in GroupKFold(n_splits=5).split(standard, groups=standard["subject_id"]):
        model = make_iforest().fit(standard[ANOMALY_FEATURES].iloc[train_idx])
        held_out_rates.append(float((model.predict(standard[ANOMALY_FEATURES].iloc[test_idx]) == -1).mean()))
    held_out, held_out_std = float(np.mean(held_out_rates)), float(np.std(held_out_rates))
    print(f"  Held-out standard frames flagged (GroupKFold 5 by subject): {held_out:.4f} ± {held_out_std:.4f}")

    final = make_iforest().fit(standard[ANOMALY_FEATURES])
    error_rates = {
        t: round(float((final.predict(errors.loc[errors["squat_type"] == t, ANOMALY_FEATURES]) == -1).mean()), 4)
        for t in ["shallow", "good_morning"]
    }
    print(f"  Frames flagged by final model: shallow {error_rates['shallow']:.4f}, "
          f"good morning {error_rates['good_morning']:.4f} (error types never seen in training)")
    latency = inference_latency_ms(final, standard[ANOMALY_FEATURES], predict=lambda m, row: m.decision_function(row))
    print(f"\nSingle-frame inference: {latency:.2f} ms (median)")

    metrics = {
        "contamination": ANOMALY_CONTAMINATION,
        "n_estimators": 100,
        "n_training_samples": len(standard),
        "features": ANOMALY_FEATURES,
        "subjects": int(standard["subject_id"].nunique()),
        "held_out_standard_flag_rate": round(held_out, 4),
        "held_out_standard_flag_rate_std": round(held_out_std, 4),
        "flag_rate_by_error_type": error_rates,
        "inference_ms_median": round(latency, 2),
    }
    save(final, "anomaly_detector_if.pkl", metrics, ANOMALY_FEATURES)
    return metrics


# --- Model comparison ---

def candidate_models(balanced: bool) -> dict:
    """Library defaults for each family (tree ensembles at 100 trees), so the comparison
    reflects the model family rather than tuning effort. Scale-sensitive models get
    standardized features. `balanced` reweights classes for the imbalanced form task."""
    weight = "balanced" if balanced else None
    return {
        "logistic_regression": lambda: make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=5000, class_weight=weight)),
        "svm": lambda: make_pipeline(StandardScaler(), SVC(kernel="rbf", class_weight=weight)),
        "random_forest": lambda: make_forest(class_weight=weight),
        "xgboost": lambda: XGBClassifier(n_estimators=100, random_state=RANDOM_STATE, n_jobs=-1),
    }


def benchmark(X: pd.DataFrame, y: pd.Series, splits: list, average: str, balanced: bool) -> dict:
    labels = LabelEncoder().fit_transform(y)  # XGBoost needs 0..k-1 labels; F1 is unaffected
    results = {}
    for name, make in candidate_models(balanced).items():
        scores, fit_seconds = [], 0.0
        for train_idx, test_idx in splits:
            model = make()
            fit_kwargs = {}
            if name == "xgboost" and balanced:
                # XGBoost has no class_weight; per-sample weights give the same balancing
                fit_kwargs["sample_weight"] = compute_sample_weight("balanced", labels[train_idx])
            start = time.perf_counter()
            model.fit(X.iloc[train_idx], labels[train_idx], **fit_kwargs)
            fit_seconds += time.perf_counter() - start
            scores.append(f1_score(labels[test_idx], model.predict(X.iloc[test_idx]), average=average))
        latency = inference_latency_ms(model, X.iloc[splits[-1][1]])
        results[name] = {
            "f1": round(float(np.mean(scores)), 4),
            "std": round(float(np.std(scores)), 4),
            "fold_f1": [round(float(f), 4) for f in scores],
            "inference_ms_median": round(latency, 3),
            "fit_seconds_total": round(fit_seconds, 2),
        }
        print(f"  {name:<20} F1 {results[name]['f1']:.4f} ± {results[name]['std']:.4f}   "
              f"inference {latency:7.3f} ms   fit {fit_seconds:6.1f} s")
    return results


def compare_models() -> dict:
    phase = pd.read_csv(DATA_DIR / "phase_training.csv")
    banner(f"MODEL COMPARISON: PHASE DETECTOR  macro F1, GroupKFold(5) by subject, {len(phase)} frames")
    phase_results = benchmark(phase[FEATURE_NAMES], phase["phase_label"], phase_splits(phase), "macro", False)

    form = pd.read_csv(DATA_DIR / "form_quality_rep_training.csv")
    y = (form["form_label"] == "bad").astype(int)
    banner(f"MODEL COMPARISON: FORM QUALITY  F1 (bad = positive), StratifiedGroupKFold(4) by subject, "
           f"{len(form)} reps")
    form_results = benchmark(form[REP_FEATURE_NAMES], y, form_splits(form, y), "binary", True)

    return {
        "deployed": "random_forest",
        "hyperparameters": "library defaults; Random Forest and XGBoost at 100 trees; "
                           "Logistic Regression and SVM (RBF) on standardized features",
        "inference": "median single-sample predict latency, single-threaded",
        "phase_detector": {
            "metric": "macro F1",
            "validation": "GroupKFold 5-fold by subject",
            "n_samples": len(phase),
            "models": phase_results,
        },
        "form_quality_rep_level": {
            "metric": "binary F1, bad = positive",
            "validation": "StratifiedGroupKFold 4-fold by subject (one bad-form subject held out per fold)",
            "class_balancing": "class_weight='balanced' (sample weights for XGBoost)",
            "n_samples": len(form),
            "models": form_results,
        },
    }


def main() -> None:
    squat = pd.read_csv(DATA_DIR / "squat.csv", usecols=["subject_id", "squat_type"])
    summary = {
        "phase_detector": train_phase_detector(),
        "form_quality_rep_level": train_form_quality(),
        "anomaly_detector": train_anomaly_detector(),
        "dataset": "Zenodo squat posture (DOI: 10.5281/zenodo.18859797)",
        "subjects": int(squat["subject_id"].nunique()),
        "squat_types": sorted(squat["squat_type"].unique()),
    }
    (MODELS_DIR / "model_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    comparison = compare_models()
    # The comparison's Random Forest must reproduce the deployed model's CV score
    for task in ("phase_detector", "form_quality_rep_level"):
        assert comparison[task]["models"]["random_forest"]["f1"] == summary[task]["f1"], task
    (MODELS_DIR / "model_comparison.json").write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    print(f"\nSaved models, model_summary.json, and model_comparison.json to {MODELS_DIR}")


if __name__ == "__main__":
    main()
