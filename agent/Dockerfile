# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# System deps
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    curl ca-certificates tini && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./

EXPOSE 8080
ENTRYPOINT ["tini", "--"]
# ADK Web/API server. It will pick ROOT agent from adk_app.py (root_agent)
CMD ["adk", "web", "--agent", "adk_app:root_agent", "--host", "0.0.0.0", "--port", "8080"]
