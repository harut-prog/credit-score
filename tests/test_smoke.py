def test_predict_returns_valid_response(client, valid_payload):
    response = client.post("/v1/predict", json=valid_payload)
    body = response.json()

    assert response.status_code == 200
    assert 0.0 <= body["score"] <= 1.0
    assert isinstance(body["arrear"], bool)
    assert body["latency_ms"] > 0
    assert body["model_version"]
    assert body["request_id"]


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["state"] == "ok"


def test_ready_endpoint(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["state"] == "ready"


def test_same_input_gives_same_score(client, valid_payload):
    r1 = client.post("/v1/predict", json=valid_payload).json()
    r2 = client.post("/v1/predict", json=valid_payload).json()

    assert r1["score"] == r2["score"]
    assert r1["arrear"] == r2["arrear"]
    assert r1["request_id"] != r2["request_id"]