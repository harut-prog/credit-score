import logging
import time
import uuid
from contextlib import asynccontextmanager

import joblib
import pandas as pd
from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import JSONResponse

from credit import db
from credit.config import settings
from credit.service.models import BatchFeatures, BatchPrediction, Features, Prediction

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    bundle = joblib.load(settings.MODEL_PATH)
    app.state.pipeline = bundle["pipeline"]
    app.state.metadata = bundle["metadata"]
    app.state.model_version = bundle["metadata"]["model_version"]

    app.state.db_enabled = bool(settings.database_url)
    if app.state.db_enabled:
        db.init()

    yield
    app.state.pipeline = None


app = FastAPI(title="Probability of a serious delay", version="1.1", lifespan=lifespan)


@app.get('/health')
def health():
    return {"state": "ok", "model_version": getattr(app.state, "model_version", "unknown")}


@app.get('/ready')
def ready():
    return {"state": "ready"}


@app.post('/v1/predict', response_model=Prediction)
def predict(X: Features, bg: BackgroundTasks):
    start_time = time.perf_counter()
    request_id = str(uuid.uuid4())

    payload = X.model_dump()
    payload["monthly_income_missing"] = int(payload["monthly_income"] is None)

    status_code, score = 200, None
    try:
        frame = pd.DataFrame([payload]).reindex(columns=app.state.metadata["features"])
        score = float(app.state.pipeline.predict_proba(frame)[0, 1])
    except Exception:
        logger.exception("inference failed for %s", request_id)
        status_code = 500

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    model_version = app.state.model_version

    if app.state.db_enabled:
        bg.add_task(db.save_prediction, request_id, payload, score, model_version, latency_ms, status_code)

    if status_code == 500:
        return JSONResponse(status_code=500, content={"detail": "inference failed", "request_id": request_id})

    arrear = score >= app.state.metadata["threshold_lr"]

    return Prediction(
        request_id=request_id,
        model_version=model_version,
        arrear=arrear,
        score=score,
        latency_ms=latency_ms,
        status_code=status_code
    )


@app.post('/v1/predict/batch', response_model=BatchPrediction)
def predict_batch(X: BatchFeatures, bg: BackgroundTasks):
    start_time = time.perf_counter()
    request_ids = [str(uuid.uuid4()) for _ in X.rows]

    payloads = [row.model_dump() for row in X.rows]
    for payload in payloads:
        payload["monthly_income_missing"] = int(payload["monthly_income"] is None)

    status_code, scores = 200, None
    try:
        frame = pd.DataFrame(payloads).reindex(columns=app.state.metadata["features"])
        scores = app.state.pipeline.predict_proba(frame)[:, 1].tolist()
    except Exception:
        logger.exception("batch inference failed for %s", request_ids[0])
        status_code = 500

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    model_version = app.state.model_version

    if app.state.db_enabled and scores is not None:
        bg.add_task(db.save_predictions, request_ids, payloads, scores, model_version, latency_ms, status_code)

    if status_code == 500:
        return JSONResponse(status_code=500, content={"detail": "inference failed", "request_ids": request_ids})

    threshold = app.state.metadata["threshold_lr"]
    arrear = [score >= threshold for score in scores]

    return BatchPrediction(
        request_ids=request_ids,
        model_version=model_version,
        arrear=arrear,
        scores=scores,
        latency_ms=latency_ms,
        status_code=status_code
    )