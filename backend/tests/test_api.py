from fastapi.testclient import TestClient

from app.main import create_app


def test_healthz_and_auth(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("WEB_PASSWORD", "pw-test")
    monkeypatch.setenv("APP_CONFIG", str(tmp_path / "missing.json"))
    app = create_app()
    client = TestClient(app)
    assert client.get("/healthz").json() == {"ok": True}
    assert client.get("/api/status").status_code == 401
    token = client.post("/api/login", json={"password": "pw-test"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/status", headers=headers).status_code == 200
    maps = client.get("/api/maps/status", headers=headers)
    assert maps.status_code == 200
    assert maps.json()["provider"]["web_service_key_configured"] is False
    missing_place = client.post("/api/maps/navigation", headers=headers, json={"destination": "家"})
    assert missing_place.status_code == 422
