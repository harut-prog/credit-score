import argparse
import sys
import tempfile
from pathlib import Path

import mlflow
import pandas as pd
import pandera.pandas as pa

from credit.config import settings

RENAME = {
    "RevolvingUtilizationOfUnsecuredLines": "unsecured_lines",
    "NumberOfTime30-59DaysPastDueNotWorse": "past_30_59",
    "DebtRatio": "debt_ratio",
    "MonthlyIncome": "monthly_income",
    "NumberOfOpenCreditLinesAndLoans": "credit_lines",
    "NumberOfTimes90DaysLate": "past_90",
    "NumberRealEstateLoansOrLines": "real_estate",
    "NumberOfTime60-89DaysPastDueNotWorse": "past_60_89",
    "NumberOfDependents": "dependents",
}

ROWS = pa.DataFrameSchema(
    {
        "SeriousDlqin2yrs": pa.Column("int64", pa.Check.isin([0, 1])),
        "unsecured_lines": pa.Column("float64", pa.Check.ge(0)),
        "age": pa.Column("int64", pa.Check.in_range(18, 120)),
        "past_30_59": pa.Column("int64", pa.Check.in_range(0, 95)),
        "past_90": pa.Column("int64", pa.Check.in_range(0, 95)),
        "past_60_89": pa.Column("int64", pa.Check.in_range(0, 95)),
        "debt_ratio": pa.Column("float64", pa.Check.ge(0)),
        "monthly_income": pa.Column("float64", pa.Check.ge(0), nullable=True),
        "credit_lines": pa.Column("int64", pa.Check.ge(0)),
        "real_estate": pa.Column("int64", pa.Check.ge(0)),
        "dependents": pa.Column(
            "float64",
            [pa.Check.ge(0), pa.Check(lambda s: s % 1 == 0)],
            nullable=True,
        ),
    },
    index=pa.Index("int64", unique=True),
    strict=True,
)

EXPORT = pa.DataFrameSchema(
    columns=ROWS.columns,
    index=ROWS.index,
    checks=[
        pa.Check(
            lambda df: len(df) >= 140_000,
            error="Выгрузка неполная: меньше 140000 строк",
        ),
        pa.Check(
            lambda df: 0.05 <= df["SeriousDlqin2yrs"].mean() <= 0.08,
            error="Доля просрочки вне диапазона 5-8%",
        ),
        pa.Check(
            lambda df: 4000 <= df["monthly_income"].median() <= 7000,
            error="Медиана дохода вне диапазона 4000-7000",
        ),
    ],
    strict=True,
)


def load_raw(path: str | Path) -> pd.DataFrame:
    raw = pd.read_csv(path, index_col=0).rename(columns=RENAME)
    return raw


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    invalid = (
        raw["past_30_59"].isin([96, 98])
        | raw["past_60_89"].isin([96, 98])
        | raw["past_90"].isin([96, 98])
        | (raw["age"] == 0)
    )
    clean = raw.loc[~invalid].copy()
    assert not clean[["past_30_59", "past_60_89", "past_90"]].isin([96, 98]).any().any()
    assert not clean["age"].eq(0).any()

    return clean


def load_clean(path):
    df = clean(load_raw(path))
    return EXPORT.validate(df, lazy=True)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--data', type=Path, default=Path('data/credit_score.csv')
    )
    args = parser.parse_args()

    mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
    mlflow.set_experiment("credit-data-validation")

    try:
        with mlflow.start_run(run_name="validate"):
            mlflow.log_param("data_path", str(args.data))

            try:
                df = load_clean(args.data)
            except pa.errors.SchemaErrors as exc:
                mlflow.set_tag("valid", "false")

                with tempfile.TemporaryDirectory() as directory:
                    report = Path(directory) / "failure_cases.csv"
                    exc.failure_cases.to_csv(report, index=False)
                    mlflow.log_artifact(str(report))

                raise

            mlflow.set_tag("valid", "true")
            mlflow.log_metrics({
                "rows": len(df),
                "default_rate": float(df['SeriousDlqin2yrs'].mean()),
                "median_income": float(df["monthly_income"].median())
            })
            print(f"Проверка пройдена: {len(df)} строк")
    except pa.errors.SchemaErrors as exc:
        print(exc)
        return 1

    return 0



if __name__ == "__main__":
    raise SystemExit(main())
