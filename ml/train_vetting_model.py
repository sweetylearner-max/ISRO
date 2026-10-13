"""Train the ExoSeer vetting classifier and export backend/models/vetting_xgb.joblib.

Downloads the NASA Exoplanet Archive Kepler KOI cumulative table (vendored to
backend/data/koi_cumulative.csv), builds a feature matrix whose columns match
exactly `app.exoseer_core.vet.MODEL_FEATURES`, labels rows from koi_disposition
(+ koi_fpflag_ss to separate eclipsing binaries), trains a multiclass XGBoost
model, prints metrics, and saves the model. Run from backend/.venv:

    cd backend && .venv/bin/python ../ml/train_vetting_model.py

The notebooks ml/01_*.ipynb and ml/02_*.ipynb document this same procedure.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from app.exoseer_core.vet import CLASSES, MODEL_FEATURES  # noqa: E402

DATA_CSV = BACKEND / "data" / "koi_cumulative.csv"
MODEL_OUT = BACKEND / "models" / "vetting_xgb.joblib"

# NASA Exoplanet Archive TAP service (cumulative KOI table).
TAP = (
    "https://exoplanetarchive.ipac.caltech.edu/TAP/sync?query="
    "select+koi_disposition,koi_period,koi_duration,koi_depth,koi_model_snr,"
    "koi_prad,koi_srad,koi_steff,koi_slogg,koi_fpflag_ss,koi_fpflag_nt,"
    "koi_fpflag_co,koi_fpflag_ec+from+cumulative&format=csv"
)


def download_koi() -> pd.DataFrame:
    if DATA_CSV.exists():
        print(f"[data] using vendored {DATA_CSV}")
        return pd.read_csv(DATA_CSV)
    print("[data] downloading KOI cumulative table from NASA Exoplanet Archive…")
    df = pd.read_csv(TAP)
    DATA_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(DATA_CSV, index=False)
    print(f"[data] vendored {len(df)} rows -> {DATA_CSV}")
    return df


def label_row(disp: str, fpflag_ss) -> str | None:
    if disp == "CONFIRMED":
        return "planet_candidate"
    if disp == "FALSE POSITIVE":
        # Stellar-eclipse flag -> eclipsing binary; otherwise other/variable.
        return "eclipsing_binary" if int(fpflag_ss or 0) == 1 else "variable_or_other"
    return None  # drop CANDIDATE (ambiguous)


def build_dataset(df: pd.DataFrame):
    df = df.copy()
    df["label"] = [label_row(d, s) for d, s in zip(df["koi_disposition"], df["koi_fpflag_ss"])]
    df = df[df["label"].notna()]

    # Map KOI columns -> MODEL_FEATURES (must match vet.build_features()).
    feat = pd.DataFrame(
        {
            "period": df["koi_period"],
            "duration_hours": df["koi_duration"],
            "depth_ppm": df["koi_depth"],
            "snr": df["koi_model_snr"],
            "implied_radius_rearth": df["koi_prad"],
            "srad": df["koi_srad"],
            "steff": df["koi_steff"],
            "slogg": df["koi_slogg"],
        }
    )
    feat["duration_over_period"] = (feat["duration_hours"] / 24.0) / feat["period"]
    feat["depth_snr"] = feat["depth_ppm"] * feat["snr"]
    feat = feat[MODEL_FEATURES]  # enforce exact column order

    y = df["label"].to_numpy()
    # Impute missing stellar/measured values with medians (model is tree-based).
    feat = feat.replace([np.inf, -np.inf], np.nan)
    feat = feat.fillna(feat.median(numeric_only=True))
    return feat.to_numpy(dtype=float), y


def main() -> None:
    from sklearn.metrics import classification_report, confusion_matrix
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import LabelEncoder
    from xgboost import XGBClassifier
    import joblib

    df = download_koi()
    X, y = build_dataset(df)
    print(f"[data] {X.shape[0]} labelled rows, {X.shape[1]} features")
    for c in CLASSES:
        print(f"       {c:20s} {(y == c).sum()}")

    # XGBoost needs integer labels; keep the name mapping to save alongside.
    le = LabelEncoder().fit(y)
    y_enc = le.transform(y)

    X_tr, X_te, ytr_enc, yte_enc = train_test_split(
        X, y_enc, test_size=0.2, random_state=42, stratify=y_enc
    )

    # Class imbalance -> inverse-frequency sample weights.
    vals, counts = np.unique(ytr_enc, return_counts=True)
    w = {v: len(ytr_enc) / (len(vals) * n) for v, n in zip(vals, counts)}
    sample_weight = np.array([w[v] for v in ytr_enc])

    model = XGBClassifier(
        n_estimators=400,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        min_child_weight=2,
        objective="multi:softprob",
        eval_metric="mlogloss",
        random_state=42,
        n_jobs=4,
    )
    model.fit(X_tr, ytr_enc, sample_weight=sample_weight)

    class_names = list(le.classes_)  # index i <-> predict_proba column i
    y_pred = model.predict(X_te)
    print("\n=== Test metrics ===")
    print(classification_report(yte_enc, y_pred, target_names=class_names, digits=3))
    print("Confusion matrix (rows=true, cols=pred), classes:", class_names)
    print(confusion_matrix(yte_enc, y_pred))
    baseline = counts.max() / counts.sum()
    print(f"Majority-class baseline accuracy: {baseline:.3f}")

    # Save model + class-name mapping so the engine maps proba columns by name.
    MODEL_OUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "classes": class_names, "features": MODEL_FEATURES}, MODEL_OUT)
    print(f"\n[model] saved -> {MODEL_OUT}  classes={class_names}")


if __name__ == "__main__":
    main()
