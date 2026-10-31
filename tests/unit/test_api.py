from fastapi.testclient import TestClient
from src.fraud.serving.api import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["ok", "healthy"]
    assert "model_loaded" in data
