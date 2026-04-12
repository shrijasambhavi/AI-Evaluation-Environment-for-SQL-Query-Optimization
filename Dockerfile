FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl build-essential sqlite3 && \
    rm -rf /var/lib/apt/lists/*

COPY . /app

RUN pip install --no-cache-dir uvicorn fastapi "openenv-core[core]>=0.2.2" pydantic

ENV PYTHONPATH="/app"

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]
