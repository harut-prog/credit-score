import json
from pathlib import Path
from types import SimpleNamespace

import joblib
import pytest
from mlflow.exceptions import MlflowException

from credit import model_store


def test_registry_model_and_metadata_use_same_version(monkeypatch):
    bundle = joblib.load("artifacts/baseline_logreg.joblib")
    calls = []

    class FakeClient:
        def get_model_version_by_alias(self, name, alias):
            assert (name, alias) == ("credit-score-logreg", "champion")
            return SimpleNamespace(version="7", run_id="run-7")

        def download_artifacts(self, run_id, artifact, folder):
            assert (run_id, artifact) == ("run-7", "metadata.json")
            path = Path(folder) / artifact
            path.write_text(json.dumps(bundle["metadata"]), encoding="utf-8")
            return str(path)

    def fake_load(uri):
        calls.append(uri)
        return bundle["pipeline"]

    monkeypatch.setattr(model_store.settings, "MODEL_NAME", "credit-score-logreg")
    monkeypatch.setattr(model_store.settings, "MODEL_ALIAS", "champion")
    monkeypatch.setattr(model_store, "MlflowClient", FakeClient)
    monkeypatch.setattr(model_store.mlflow, "set_tracking_uri", lambda _: None)
    monkeypatch.setattr(model_store.mlflow.sklearn, "load_model", fake_load)
    pipeline, metadata, identity = model_store.load_bundle()

    assert pipeline is bundle["pipeline"]
    assert metadata == bundle["metadata"]
    assert calls == ["models:/credit-score-logreg/7"]
    assert identity["model_version"] == "7"
    assert identity["run_id"] == "run-7"
    assert identity["model_source"] == "registry"


def test_missing_alias_fails_without_file_fallback(monkeypatch):
    class FakeClient:
        def get_model_version_by_alias(self, _name, _alias):
            raise MlflowException("Alias missing", error_code="RESOURCE_DOES_NOT_EXIST")

    def forbidden_fallback(_path):
        raise AssertionError("File fallback must not hide a Registry failure")

    monkeypatch.setattr(model_store.settings, "MODEL_NAME", "credit-score-logreg")
    monkeypatch.setattr(model_store, "MlflowClient", FakeClient)
    monkeypatch.setattr(model_store.mlflow, "set_tracking_uri", lambda _: None)
    monkeypatch.setattr(model_store.joblib, "load", forbidden_fallback)

    with pytest.raises(MlflowException, match="Alias missing"):
        model_store.load_bundle()
