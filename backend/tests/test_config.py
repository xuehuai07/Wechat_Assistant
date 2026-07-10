from pathlib import Path

from app.config import load_settings


def test_load_settings_from_example(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("WEB_PASSWORD", "pw-test")
    settings = load_settings(Path("config.example.json"))
    assert settings.web.host == "127.0.0.1"
    assert settings.web.port == 6500
    assert settings.web.serve_frontend is False
    assert settings.model.provider == "deepseek"
    assert settings.deepseek_api_key == "sk-test"
    assert "deepseek_api_key" not in settings.public_summary()


def test_app_serve_frontend_env_overrides_config(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("WEB_PASSWORD", "pw-test")
    monkeypatch.setenv("APP_SERVE_FRONTEND", "1")
    settings = load_settings(Path("config.example.json"))
    assert settings.web.serve_frontend is True
