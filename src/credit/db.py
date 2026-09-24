import psycopg
from psycopg.types.json import Json

from credit.config import settings

QUERY = """
    CREATE TABLE IF NOT EXISTS predictions (
        request_id uuid PRIMARY KEY,
        ts timestamptz NOT NULL DEFAULT now(),
        model_version text NOT NULL,
        features jsonb NOT NULL,
        score numeric(5,3),
        latency_ms integer,
        status_code integer
    )
"""

def init() -> None:
    if not settings.database_url:
        return None  # noqa: RET501

    with psycopg.connect(settings.database_url) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(12345)").fetchone()
        conn.execute(QUERY)


def save_prediction(
    request_id: str, 
    features: dict, 
    score: float | None,
    model_version: str, 
    latency_ms: float,
    status_code: int
) -> None:
    if not settings.database_url:
        return None  # noqa: RET501

    with psycopg.connect(settings.database_url) as conn:
        conn.execute(
            "INSERT INTO predictions (request_id, features, score, model_version, latency_ms, status_code) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (request_id, Json(features), score, model_version, latency_ms, status_code),
        )


def save_predictions(
    request_ids: list[str],
    features: list[dict],
    scores: list[float],
    model_version: str,
    latency_ms: float,
    status_code: int
) -> None:
    if not settings.database_url:
        return None  # noqa: RET501

    rows = [
        (request_id, Json(payload), score, model_version, latency_ms, status_code)
        for request_id, payload, score in zip(request_ids, features, scores)
    ]

    with psycopg.connect(settings.database_url) as conn:  # noqa: SIM117
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO predictions (request_id, features, score, model_version, latency_ms, status_code) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                rows,
            )