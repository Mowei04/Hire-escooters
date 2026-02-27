"""Health endpoint smoke test."""

from app import app


def test_health_check() -> None:
    """Verify service health endpoint contract."""
    client = app.test_client()
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
