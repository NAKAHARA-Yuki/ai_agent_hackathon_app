# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# System deps
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    ca-certificates tini && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ADK runtime loads root agent from adk_app.py
COPY adk_app.py ./

EXPOSE 8080
ENTRYPOINT ["tini", "--"]
# ADK API server with CORS configured for local dev; Cloud Run listens on $PORT (8080)
CMD ["adk", "api_server", "--agent", "adk_app:root_agent", "--host", "0.0.0.0", "--port", "8080", "--allow_origins", "http://localhost:4200"]
