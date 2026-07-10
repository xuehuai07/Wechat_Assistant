#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install Docker Desktop or Docker Engine first." >&2
  exit 1
fi

docker compose config -q
docker build --tag wechat-assistant:0.1.0 .
docker run --rm -e DEEPSEEK_API_KEY=verification-only -e WEB_PASSWORD=verification-only wechat-assistant:0.1.0 \
  python -c "from app.main import create_app; assert create_app().title == 'Private WeChat Agent'"

echo "Docker configuration and image build verified."
