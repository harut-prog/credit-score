import json
import math
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid

BASE = os.environ.get("INGRESS_URL", "http://127.0.0.1").rstrip("/")
HOST = os.environ.get("INGRESS_HOST", "credit.localhost")
PAYLOAD = {
    "unsecured_lines": 0.3, "age": 35, "past_30_59": 0, "past_90": 0,
    "past_60_89": 0, "debt_ratio": 0.5, "monthly_income": 5000,
    "credit_lines": 5, "real_estate": 1, "dependents": 2,
}


def request(path, payload=None, retries=0):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE + path, data=data,
        headers={"Host": HOST, "Content-Type": "application/json"},
    )
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code not in {502, 503, 504} or attempt == retries:
                raise
            reason = f"HTTP {error.code} {error.reason}"
        except urllib.error.URLError as error:
            if attempt == retries:
                raise
            reason = str(error.reason)

        delay = min(2 + attempt, 10)
        print(
            f"Ingress is not ready for {path} ({reason}); "
            f"retrying in {delay}s ({attempt + 1}/{retries})",
            flush=True,
        )
        time.sleep(delay)


def main():
    health = request("/health", retries=20)

    assert health["state"] == "ok", health
    assert health["model_source"] == "registry", health
    assert health["model_name"] == "credit-score-logreg", health
    assert str(health["model_version"]).isdigit(), health
    assert request("/ready", retries=20)["state"] == "ready"

    result = request("/v1/predict", PAYLOAD, retries=6)
    request_id = str(uuid.UUID(result["request_id"]))

    assert result["status_code"] == 200, result
    assert 0 <= result["score"] <= 1, result
    assert result["model_version"] == health["model_version"], result
    assert result["arrear"] == (result["score"] >= health["threshold"]), result

    query = (
        "SELECT json_build_object('request_id',request_id,'score',score,"
        "'model_version',model_version,'status_code',status_code) "
        f"FROM predictions WHERE request_id='{request_id}';"
    )
    row = None
    for _ in range(30):
        text = subprocess.check_output([
            "kubectl", "exec", "deploy/postgres", "--", "psql",
            "-U", "postgres", "-d", "credit", "-tAc", query,
        ], text=True).strip()
        if text:
            lines = text.splitlines()
            assert len(lines) == 1, text
            row = json.loads(lines[0])
            break
        time.sleep(0.5)

    assert row is not None, f"No DB row for request_id={request_id}"
    assert row["request_id"] == request_id, row
    assert row["status_code"] == 200, row
    assert row["model_version"] == result["model_version"], row
    assert math.isclose(row["score"], result["score"], rel_tol=1e-10, abs_tol=1e-12), row
    print(json.dumps({"health": health, "prediction": result, "db_row": row}, indent=2))


if __name__ == "__main__":
    main()
