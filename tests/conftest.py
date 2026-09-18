import pytest
from fastapi.testclient import TestClient

from credit.service.app import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def valid_payload():
    return {
        "unsecured_lines": 0.3,
        "age": 35,
        "past_30_59": 0,
        "past_90": 0,
        "past_60_89": 0,
        "debt_ratio": 0.5,
        "monthly_income": 5000.0,
        "credit_lines": 5,
        "real_estate": 1,
        "dependents": 2,
    }