import logging
import time
import uuid
from contextlib import asynccontextmanager

import pandas as pd
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from credit import db
from credit.config import settings
from credit.model_store import load_bundle
from credit.service.models import BatchFeatures, BatchPrediction, Features, Prediction

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    pipeline, metadata, identity = load_bundle()
    app.state.pipeline = pipeline
    app.state.metadata = metadata
    app.state.model_identity = identity
    app.state.model_version = identity["model_version"]
    app.state.db_enabled = bool(settings.database_url)
    if app.state.db_enabled:
        db.init()
    yield
    app.state.pipeline = None


app = FastAPI(title="Probability of a serious delay", version="1.1", lifespan=lifespan)


@app.get("/health")
def health():
    return {
        "state": "ok", 
        **app.state.model_identity,
        "threshold": app.state.metadata["threshold_lr"],
        "log_level": settings.LOG_LEVEL,
    }


@app.get('/ready')
def ready():
    pipeline = getattr(app.state, "pipeline", None)
    metadata = getattr(app.state, "metadata", None)
    model_ready = pipeline is not None and callable(getattr(pipeline, "predict_proba", None))
    metadata_ready = (
        isinstance(metadata, dict)
        and bool(metadata.get("features"))
        and isinstance(metadata.get("threshold_lr"), (int, float))
    )
    if not model_ready or not metadata_ready:
        return JSONResponse(status_code=503, content={"state": "not_ready"})
    return {"state": "ready"}


def save_with_logging(*args):
    try:
        db.save_prediction(*args)
    except Exception:
        logger.exception("failed to save prediction %s", args[0])
        raise


def save_batch_with_logging(*args):
    try:
        db.save_predictions(*args)
    except Exception:
        logger.exception("failed to save batch starting with %s", args[0][0])
        raise


@app.exception_handler(RequestValidationError)
def valid_exception_handler(request: Request, exc: RequestValidationError):
    if request.url.path != '/v1/predict':
        return JSONResponse(status_code=422, content={"detail": jsonable_encoder(exc.errors())})

    request_id = str(uuid.uuid4())

    if app.state.db_enabled:
        payload = exc.body
        save_with_logging(request_id, payload, None, app.state.model_version, 0, 422)

    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(exc.errors()), "request_id": request_id})


@app.post('/v1/predict', response_model=Prediction)
def predict(X: Features, bg: BackgroundTasks):
    start_time = time.perf_counter()
    request_id = str(uuid.uuid4())

    payload = X.model_dump()

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
        bg.add_task(save_with_logging, request_id, payload, score, model_version, latency_ms, status_code)

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

    status_code, scores = 200, None
    try:
        frame = pd.DataFrame(payloads).reindex(columns=app.state.metadata["features"])
        scores = app.state.pipeline.predict_proba(frame)[:, 1].tolist()
    except Exception:
        logger.exception("batch inference failed for %s", request_ids[0])
        status_code = 500

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    model_version = app.state.model_version

    if app.state.db_enabled:
        logged_scores = scores if scores is not None else [None] * len(request_ids)
        bg.add_task(
            save_batch_with_logging, request_ids, payloads, logged_scores, model_version, latency_ms, status_code
        )

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
