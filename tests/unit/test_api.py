from fastapi.testclient import TestClient

from src.fraud.serving.api import app

client = TestClient(app)


def transaction(transaction_id="txn-1"):
    value = {
        "transaction_id": transaction_id,
        "Time": 100.0,
        "Amount": 42.5,
    }
    value.update({f"V{index}": float(index - 14) / 10 for index in range(1, 29)})
    return value


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded", "ok"]
    assert "model_version" in data
    assert "mlflow_uri" in data


def test_metrics():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "fraud_api_requests_total" in response.text


def test_predict_success():
    response = client.post("/predict", json=transaction())
    assert response.status_code == 200
    data = response.json()
    assert data["transaction_id"] == "txn-1"
    assert 0 <= data["fraud_probability"] <= 1
    assert data["decision"] in {"FRAUD", "LEGIT"}
    assert len(data["top_features"]) == 3
    assert data["latency_ms"] >= 0


def test_predict_invalid_amount_returns_422():
    invalid = transaction()
    invalid["Amount"] = -1
    response = client.post("/predict", json=invalid)
    assert response.status_code == 422


def test_predict_missing_feature_returns_422():
    invalid = transaction()
    del invalid["V28"]
    response = client.post("/predict", json=invalid)
    assert response.status_code == 422


def test_predict_batch():
    response = client.post(
        "/predict_batch",
        json=[transaction("txn-1"), transaction("txn-2")],
    )
    assert response.status_code == 200
    predictions = response.json()["predictions"]
    assert [item["transaction_id"] for item in predictions] == ["txn-1", "txn-2"]
