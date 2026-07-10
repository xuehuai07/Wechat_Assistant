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
    assert client.get("/api/status", headers={"Authorization": f"Bearer {token}"}).status_code == 200
