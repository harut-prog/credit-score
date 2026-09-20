import psycopg
import pytest

from credit.config import settings


@pytest.mark.integrations
def test_prediction_is_logged(client, valid_payload):
    if not client.app.state.db_enabled:
        pytest.skip("DATABASE_URL is not set or postgres is down")

    response = client.post("/v1/predict", json=valid_payload)
    request_id = response.json()["request_id"]

    with psycopg.connect(settings.database_url) as conn:
        row = conn.execute(
            "SELECT score, status_code FROM predictions WHERE request_id = %s",
            (request_id,),
        ).fetchone()

    assert row is not None
    assert row[1] == 200
    assert 0.0 <= float(row[0]) <= 1.0
