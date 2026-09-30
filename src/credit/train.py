import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from mlflow.models import infer_signature
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, precision_recall_curve, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

matplotlib.use("Agg")

RENAME = {
    "RevolvingUtilizationOfUnsecuredLines": "unsecured_lines",
    "NumberOfTime30-59DaysPastDueNotWorse": "past_30_59",
    "DebtRatio": "debt_ratio",
    "MonthlyIncome": "monthly_income",
    "NumberOfOpenCreditLinesAndLoans": "credit_lines",
    "NumberOfTimes90DaysLate": "past_90",
    "NumberRealEstateLoansOrLines": "real_estate",
    "NumberOfTime60-89DaysPastDueNotWorse": "past_60_89",
    "NumberOfDependents": "dependents",
}
FEATURES = [
    "unsecured_lines", "age", "past_30_59", "debt_ratio", "monthly_income",
    "credit_lines", "past_90", "real_estate", "past_60_89", "dependents",
]
MODEL_NAME = "credit-score-logreg"


def make_pipeline(c, class_weight):
    other = [f for f in FEATURES if f not in {"monthly_income", "dependents"}]
    preprocess = ColumnTransformer([
        ("income", Pipeline([
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
        ]), ["monthly_income"]),
        ("dependents", Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]), ["dependents"]),
        ("other", StandardScaler(), other),
    ])
    return Pipeline([
        ("preprocess", preprocess),
        ("model", LogisticRegression(
            C=c, max_iter=1000,
            class_weight=None if class_weight == "none" else class_weight,
        )),
    ])


def load_splits(path, seed):
    raw = pd.read_csv(path, index_col=0).rename(columns=RENAME)
    invalid = (
        raw["past_30_59"].isin([96, 98])
        | raw["past_60_89"].isin([96, 98])
        | raw["past_90"].isin([96, 98])
        | (raw["age"] == 0)
    )
    removed = int(invalid.sum())
    clean = raw.loc[~invalid].copy()
    assert not clean[["past_30_59", "past_60_89", "past_90"]].isin([96, 98]).any().any()
    assert not clean["age"].eq(0).any()
    x, y = clean[FEATURES], clean["SeriousDlqin2yrs"]
    xt, x_test, yt, y_test = train_test_split(
        x, y, test_size=0.2, stratify=y, random_state=seed,
    )
    x_train, x_val, y_train, y_val = train_test_split(
        xt, yt, test_size=0.25, stratify=yt, random_state=seed,
    )
    evaluation = x_val.copy()
    evaluation["target"] = y_val
    evaluation_md5 = hashlib.md5(evaluation.to_csv().encode("utf-8")).hexdigest()
    print(f"raw={len(raw)} removed={removed} clean={len(clean)}")
    print(f"train={len(x_train)} val={len(x_val)} test={len(x_test)}")
    return x_train, x_val, x_test, y_train, y_val, y_test, removed, evaluation_md5


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data/credit_score.csv"))
    parser.add_argument("--c", type=float, default=1.0)
    parser.add_argument("--class-weight", choices=["none", "balanced"], default="none")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-gain", type=float, default=0.001)
    args = parser.parse_args()
    if args.c <= 0 or args.min_gain < 0:
        parser.error("c must be positive and min-gain nonnegative")

    data_md5 = hashlib.md5(args.data.read_bytes()).hexdigest()
    git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()

    splits = load_splits(args.data, args.seed)
    x_train, x_val, x_test, y_train, y_val, y_test, removed, evaluation_md5 = splits
    pipeline = make_pipeline(args.c, args.class_weight)
    pipeline.fit(x_train, y_train)
    val_proba = pipeline.predict_proba(x_val)[:, 1]
    test_proba = pipeline.predict_proba(x_test)[:, 1]
    val_ap = float(average_precision_score(y_val, val_proba))
    precision, recall, thresholds = precision_recall_curve(y_val, val_proba)

    eligible = thresholds[recall[:-1] >= 0.70]
    threshold = float(eligible.max()) if len(eligible) else 0.0

    metadata = {
        "model_name": MODEL_NAME, "features": FEATURES, "threshold_lr": threshold,
        "data_md5": data_md5, "git_sha": git_sha, "seed": args.seed,
        "evaluation_md5": evaluation_md5, "algorithm": "LogisticRegression",
        "parameters": {"C": args.c, "class_weight": args.class_weight},
        "removed_invalid_rows": removed,
        "n_train": len(x_train), "n_validation": len(x_val), "n_test": len(x_test),
        "metrics_validation": {"average_precision": val_ap},
        "metrics_test": {
            "average_precision": float(average_precision_score(y_test, test_proba)),
            "roc_auc": float(roc_auc_score(y_test, test_proba)),
            "recall_at_threshold": float(recall_score(y_test, test_proba >= threshold)),
        },
    }

    mlflow.set_experiment("credit-score-hw3")
    client = MlflowClient()
    try:
        champion = client.get_model_version_by_alias(MODEL_NAME, "champion")
    except MlflowException as exc:
        if exc.error_code != "RESOURCE_DOES_NOT_EXIST":
            raise
        champion = None

    champion_ap = None
    if champion is not None:
        with tempfile.TemporaryDirectory() as folder:
            path = client.download_artifacts(champion.run_id, "metadata.json", folder)
            old_meta = json.loads(Path(path).read_text(encoding="utf-8"))
        if old_meta["evaluation_md5"] != evaluation_md5:
            raise RuntimeError("Validation changed; compare on the same holdout")
        old = mlflow.sklearn.load_model(f"models:/{MODEL_NAME}/{champion.version}")
        champion_ap = float(average_precision_score(y_val, old.predict_proba(x_val)[:, 1]))

    with mlflow.start_run(run_name=f"C={args.c};weight={args.class_weight}") as run:
        mlflow.log_params({
            "C": args.c, "class_weight": args.class_weight, "seed": args.seed,
            "MIN_GAIN": args.min_gain, "data_md5": data_md5,
            "git_sha": git_sha, "evaluation_md5": evaluation_md5,
        })
        mlflow.log_metrics({
            "val_average_precision": val_ap,
            "test_average_precision": metadata["metrics_test"]["average_precision"],
            "test_roc_auc": metadata["metrics_test"]["roc_auc"], "threshold": threshold,
        })
        mlflow.log_dict(metadata, "metadata.json")

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(recall, precision)
        ax.set(xlabel="Recall", ylabel="Precision", title="Credit scoring: validation PR curve")
        mlflow.log_figure(fig, "validation_pr_curve.png")
        plt.close(fig)

        info = mlflow.sklearn.log_model(
            sk_model=pipeline, name="model", registered_model_name=MODEL_NAME,
            signature=infer_signature(x_train.head(5), pipeline.predict(x_train.head(5))),
            input_example=x_train.head(5),
        )
        version = str(info.registered_model_version)
        if version == "None":
            raise RuntimeError("No registered_model_version returned")
        client.set_registered_model_alias(MODEL_NAME, "challenger", version)
        loaded = mlflow.sklearn.load_model(f"models:/{MODEL_NAME}/{version}")
        np.testing.assert_allclose(
            loaded.predict_proba(x_val.head(20)), pipeline.predict_proba(x_val.head(20)),
            rtol=1e-10, atol=1e-12,
        )

        promoted = champion_ap is None or val_ap >= champion_ap + args.min_gain
        if promoted:
            client.set_registered_model_alias(MODEL_NAME, "champion", version)
        mlflow.set_tag("gate_decision", "promoted" if promoted else "rejected")
        if champion_ap is not None:
            mlflow.log_metric("champion_val_average_precision", champion_ap)
            
        print(json.dumps({
            "run_id": run.info.run_id, "version": version, "data_md5": data_md5,
            "candidate_ap": val_ap, "champion_ap": champion_ap,
            "MIN_GAIN": args.min_gain, "promoted": bool(promoted),
        }))


if __name__ == "__main__":
    main()
