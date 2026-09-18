def test_missing_required_field_returns_422(client, valid_payload):
    payload = valid_payload.copy()
    del payload["age"]
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 422


def test_extra_field_returns_422(client, valid_payload):
    payload = valid_payload | {"favorite_color": "blue"}
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 422


def test_negative_age_returns_422(client, valid_payload):
    payload = valid_payload | {"age": -5}
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 422


def test_null_optional_fields_are_allowed(client, valid_payload):
    payload = valid_payload | {"monthly_income": None, "dependents": None}
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 200


def test_batch_returns_scores_in_order(client, valid_payload):
    rows = [valid_payload | {"age": 18 + i % 83, "debt_ratio": round(i / 1000, 3)} for i in range(500)]
    response = client.post("/v1/predict/batch", json={"rows": rows})

    assert response.status_code == 200
    body = response.json()
    assert len(body["scores"]) == 500
    assert len(body["arrear"]) == 500
    assert len(body["request_ids"]) == 500
    assert body["request_ids"][0] != body["request_ids"][1]
    assert body["status_code"] == 200
    assert body["latency_ms"] > 0

    for index in (0, 250, 499):
        single = client.post("/v1/predict", json=rows[index]).json()
        assert body["scores"][index] == single["score"]
        assert body["arrear"][index] == single["arrear"]


def test_batch_matches_single_prediction(client, valid_payload):
    single = client.post("/v1/predict", json=valid_payload).json()
    batch = client.post("/v1/predict/batch", json={"rows": [valid_payload]}).json()

    assert batch["scores"][0] == single["score"]


def test_batch_size_bounds_are_enforced(client, valid_payload):
    assert client.post("/v1/predict/batch", json={"rows": []}).status_code == 422
    assert client.post("/v1/predict/batch", json={"rows": [valid_payload] * 1001}).status_code == 422