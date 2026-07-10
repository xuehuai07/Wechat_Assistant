# syntax=docker/dockerfile:1
FROM node:22.23.1-alpine AS frontend-build

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    APP_SERVE_FRONTEND=1

WORKDIR /app
RUN groupadd --gid 10001 agent \
    && useradd --uid 10001 --gid agent --create-home --shell /usr/sbin/nologin agent

COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock \
    && pip check

COPY backend/ ./backend/
COPY config.example.json ./config.example.json
COPY --from=frontend-build /build/frontend/dist ./frontend/dist
RUN mkdir -p runtime/logs \
    && chown -R agent:agent /app

USER agent
EXPOSE 6500
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:6500/healthz', timeout=3).read()"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "6500"]
