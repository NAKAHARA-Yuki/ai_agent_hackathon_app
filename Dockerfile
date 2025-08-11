# ステージ1: フロントエンドのビルド
FROM node:18-alpine AS build-stage
WORKDIR /app
COPY client/package*.json ./
RUN npm install
COPY client/ .
RUN npm run build

# ステージ2: 本番環境
FROM python:3.11-slim
WORKDIR /app

# ビルドしたフロントエンドのファイルをコピー
COPY --from=build-stage /app/dist ./client/dist

# バックエンドの依存関係をインストール
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# バックエンドのコードをコピー
COPY server/ .

# 環境変数PORTをリッスン
EXPOSE 8080
ENV PORT=8080
STOPSIGNAL SIGTERM

# アプリケーションの起動（Cloud RunのPORTに対応）
CMD ["/bin/sh", "-c", "exec gunicorn --worker-class gevent --bind 0.0.0.0:${PORT:-8080} --timeout 120 --graceful-timeout 5 app:app"]