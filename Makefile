.PHONY: backend-dev frontend-dev test lint bootstrap

bootstrap:
	export PATH="/usr/local/opt/node@22/bin:/opt/homebrew/opt/node@22/bin:$$PATH"; \
	python3.12 -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -e ".[dev]"
	export PATH="/usr/local/opt/node@22/bin:/opt/homebrew/opt/node@22/bin:$$PATH"; cd frontend && npm install
	test -f config.json || cp config.example.json config.json
	test -f .env || cp .env.example .env

backend-dev:
	PYTHONPATH=backend .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 6500 --reload

frontend-dev:
	export PATH="/usr/local/opt/node@22/bin:/opt/homebrew/opt/node@22/bin:$$PATH"; cd frontend && npm run dev

test:
	PYTHONPATH=backend .venv/bin/python -m pytest

lint:
	PYTHONPATH=backend .venv/bin/ruff check backend
	export PATH="/usr/local/opt/node@22/bin:/opt/homebrew/opt/node@22/bin:$$PATH"; cd frontend && npm run typecheck
