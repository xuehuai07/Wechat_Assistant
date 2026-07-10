from pathlib import Path


def test_docker_assets_exclude_local_secrets_and_runtime_data():
    root = Path(__file__).resolve().parents[2]
    ignored = (root / ".dockerignore").read_text(encoding="utf-8")
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")

    assert ".env" in ignored
    assert "config.json" in ignored
    assert "profile.local.json" in ignored
    assert "runtime/" in ignored
    assert "COPY ." not in dockerfile
    assert "USER agent" in dockerfile
    assert "HEALTHCHECK" in dockerfile


def test_compose_keeps_the_web_service_on_loopback_and_runtime_in_a_named_volume():
    root = Path(__file__).resolve().parents[2]
    compose = (root / "compose.yaml").read_text(encoding="utf-8")

    assert "host_ip: 127.0.0.1" in compose
    assert "target: /app/runtime" in compose
    assert "name: wechat-assistant-runtime" in compose
    assert "read_only: true" in compose


def test_dockerfile_uses_pinned_build_and_runtime_images():
    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    lockfile = (root / "requirements.lock").read_text(encoding="utf-8")

    assert "FROM node:22.23.1-alpine AS frontend-build" in dockerfile
    assert "FROM python:3.12.13-slim AS runtime" in dockerfile
    assert "fastapi==0.139.0" in lockfile
    assert "langgraph==1.2.8" in lockfile
