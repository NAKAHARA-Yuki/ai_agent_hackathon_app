# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    PYTHONPATH=/app:/app/agents

WORKDIR /app

# System deps
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    ca-certificates tini curl gnupg && \
    # Install Node.js (for npx to run MCP server)
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ADK api_server will load agents from ./agents
COPY agents ./agents
# shared（リポジトリ上位）に依存しない設計へ戻す
# ルートに加えて agents ディレクトリも import path に含める
ENV PYTHONPATH=/app:/app/agents

EXPOSE 8080
ENTRYPOINT ["tini", "--"]
# ADK API server with CORS configured for local dev; serve agents from /app/agents
CMD ["adk", "api_server", "--host", "0.0.0.0", "--port", "8080", "--log_level", "debug", "--allow_origins", "http://localhost:4200", "./agents"]
