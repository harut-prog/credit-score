import psycopg
import pytest

from credit.config import settings


@pytest.mark.integrations
def test_prediction_is_logged(client, valid_payload):
    if not client.app.state.db_enabled:
        pytest.skip("DATABASE_URL is not set or postgres is down")

    response = client.post("/v1/predict", json=valid_payload)
    assert response.status_code == 200
    request_id = response.json()["request_id"]

    with psycopg.connect(settings.database_url) as conn:
        row = conn.execute(
            "SELECT score, status_code, features->>'age', model_version FROM predictions WHERE request_id = %s",
            (request_id,),
        ).fetchone()

    assert row is not None
    assert row[1] == 200
    assert 0.0 <= float(row[0]) <= 1.0
    assert row[2] == str(valid_payload["age"])
    assert row[3] == response.json()["model_version"]


@pytest.mark.integrations
def test_invalid_payload(client, valid_payload):
    if not client.app.state.db_enabled:
        pytest.skip("DATABASE_URL is not set or postgres is down")

    invalid_payload = valid_payload | {"unknown": "unknown"}
    response = client.post('/v1/predict', json=invalid_payload)
    assert response.status_code == 422

    request_id = response.json()["request_id"]
    with psycopg.connect(settings.database_url) as conn:
        row = conn.execute(
            "SELECT score, status_code FROM predictions WHERE request_id = %s",
            (request_id,),
        ).fetchone()

    assert row is not None
    assert row[0] is None
    assert row[1] == 422


@pytest.mark.integrations
def test_inference_failure_is_logged(client, valid_payload, monkeypatch):
    if not client.app.state.db_enabled:
        pytest.skip("PostgreSQL is not configured")

    class BrokenPipeline:
        def predict_proba(self, _frame):
            raise RuntimeError("test failure")

    monkeypatch.setattr(client.app.state, "pipeline", BrokenPipeline())
    response = client.post("/v1/predict", json=valid_payload)
    assert response.status_code == 500
    request_id = response.json()["request_id"]
    with psycopg.connect(settings.database_url) as conn:
        row = conn.execute(
            "SELECT score, status_code FROM predictions WHERE request_id = %s", (request_id,)
        ).fetchone()
    assert row == (None, 500)
