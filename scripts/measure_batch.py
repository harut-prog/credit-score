import httpx
import numpy as np

URL = "http://127.0.0.1:8080/v1/predict/batch"
REPEATS = 10
ROW = {
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


def measure(rows: int) -> float:
    body = {"rows": [ROW] * rows}
    latencies = []
    with httpx.Client(timeout=60) as client:
        for _ in range(REPEATS):
            response = client.post(URL, json=body)
            response.raise_for_status()
            latencies.append(response.json()["latency_ms"])
    return np.median(latencies)


one = measure(1)
batch = measure(500)
print(f"1 строка:  медиана latency_ms = {one}")
print(f"500 строк: медиана latency_ms = {batch}")
print(f"отношение: {batch / one:.2f}x")