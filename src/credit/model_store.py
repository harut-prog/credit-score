import json
import logging
import math
import tempfile
from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
from mlflow import MlflowClient

from credit.config import settings
from credit.service.models import Features

logger = logging.getLogger(__name__)


def validate_metadata(pipeline, metadata):
    if not callable(getattr(pipeline, "predict_proba", None)):
        raise ValueError("Model must support predict_proba")
    features = metadata.get("features")
    if not isinstance(features, list) or len(features) != len(set(features)):
        raise ValueError("Invalid feature list")
    if set(features) != set(Features.model_fields):
        raise ValueError("Model features differ from API schema")
    threshold = metadata.get("threshold_lr")
    if not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Invalid threshold_lr")


def load_bundle():
    if not settings.MODEL_NAME:
        bundle = joblib.load(settings.MODEL_PATH)
        validate_metadata(bundle["pipeline"], bundle["metadata"])
        return bundle["pipeline"], bundle["metadata"], {
            "model_source": "file", "model_name": bundle["metadata"].get("model_name"),
            "model_alias": None, "model_version": str(bundle["metadata"]["model_version"]),
            "run_id": None,
        }

    mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
    client = MlflowClient()

    version = client.get_model_version_by_alias(settings.MODEL_NAME, settings.MODEL_ALIAS)
    pipeline = mlflow.sklearn.load_model(f"models:/{settings.MODEL_NAME}/{version.version}")
    with tempfile.TemporaryDirectory() as folder:
        path = client.download_artifacts(version.run_id, "metadata.json", folder)
        metadata = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_metadata(pipeline, metadata)

    logger.info("Loaded registry model %s version %s alias %s", settings.MODEL_NAME, version.version, settings.MODEL_ALIAS)
    return pipeline, metadata, {
        "model_source": "registry", "model_name": settings.MODEL_NAME,
        "model_alias": settings.MODEL_ALIAS, "model_version": str(version.version),
        "run_id": version.run_id,
    }
