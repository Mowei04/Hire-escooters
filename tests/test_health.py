from server import app, init_db


def test_health_check() -> None:
    init_db()
    client = app.test_client()
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "framework": "flask"}
