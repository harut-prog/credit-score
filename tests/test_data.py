import pandas as pd
import pandera.pandas as pa
import pytest

from credit.data import EXPORT, ROWS


@pytest.fixture
def sample():
    return pd.DataFrame(
        {
            "SeriousDlqin2yrs": [0, 1],
            "unsecured_lines": [0.2, 0.7],
            "age": [35, 109],
            "past_30_59": [0, 1],
            "past_90": [0, 0],
            "past_60_89": [0, 0],
            "debt_ratio": [0.3, 0.8],
            "monthly_income": [5000.0, float("nan")],
            "credit_lines": [5, 2],
            "real_estate": [1, 0],
            "dependents": [2.0, float("nan")],
        },
        index=pd.Index([1, 2], dtype="int64"),
    )


def test_valid_rows(sample):
    assert len(ROWS.validate(sample, lazy=True)) == 2


def test_invalid_age_and_duplicate_id(sample):
    bad = sample.copy()
    bad.loc[1, "age"] = 121
    bad.index = pd.Index([1, 1], dtype="int64")
    with pytest.raises(pa.errors.SchemaErrors):
        ROWS.validate(bad, lazy=True)


def test_incomplete_export(sample):
    with pytest.raises(pa.errors.SchemaErrors):
        EXPORT.validate(sample, lazy=True)
