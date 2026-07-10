#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PATH="/usr/local/opt/node@22/bin:/opt/homebrew/opt/node@22/bin:$PATH"

if ! command -v python3.12 >/dev/null 2>&1; then
  echo "Python 3.12 is required. Install it with: brew install python@3.12" >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required for the React console. Install Node.js first." >&2
  exit 1
fi

python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"

cd frontend
npm install
cd "$ROOT"

test -f config.json || cp config.example.json config.json
test -f .env || cp .env.example .env
mkdir -p runtime/logs
chmod 700 runtime
chmod 600 .env config.json

echo "Bootstrap complete. Fill .env, then run: scripts/run-backend.sh"
