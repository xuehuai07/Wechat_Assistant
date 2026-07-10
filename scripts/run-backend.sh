#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -x .venv/bin/python ]]; then
  echo "Missing .venv. Run scripts/bootstrap-local.sh first." >&2
  exit 1
fi
if [[ ! -f .env ]]; then
  echo "Missing .env. Copy .env.example to .env and fill it." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
  echo "DEEPSEEK_API_KEY is required." >&2
  exit 1
fi
if [[ -z "${WEB_PASSWORD:-}" ]]; then
  echo "WEB_PASSWORD is required." >&2
  exit 1
fi

export PYTHONPATH="$ROOT/backend"
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 9899
