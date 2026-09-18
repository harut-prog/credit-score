from pydantic import BaseModel, Field


class Features(BaseModel):
    model_config = {"extra": "forbid"}

    unsecured_lines: float = Field(..., ge=0)
    age: int = Field(..., ge=18, le=100)
    past_30_59: int = Field(..., ge=0)
    past_90: int = Field(..., ge=0)
    past_60_89: int = Field(..., ge=0)
    debt_ratio: float = Field(..., ge=0)
    monthly_income: float | None = Field(None, ge=0)
    credit_lines: int = Field(..., ge=0)
    real_estate: int = Field(..., ge=0)
    dependents: int | None = Field(None, ge=0)


class Prediction(BaseModel):
    model_config = {"protected_namespaces": ()}

    request_id: str
    model_version: str
    arrear: bool
    score: float
    latency_ms: float
    status_code: int


class BatchFeatures(BaseModel):
    model_config = {"extra": "forbid"}

    rows: list[Features] = Field(..., min_length=1, max_length=1000)


class BatchPrediction(BaseModel):
    model_config = {"protected_namespaces": ()}

    request_ids: list[str]
    model_version: str
    arrear: list[bool]
    scores: list[float]
    latency_ms: float
    status_code: int