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
# shared ロギング/共通コード
COPY shared/ ./shared

# 環境変数PORTをリッスン
EXPOSE 8080
ENV PORT=8080 \
	LOG_LEVEL=INFO
STOPSIGNAL SIGTERM

# アプリケーションの起動（Cloud RunのPORTに対応）
# geventではなく同期ワーカー+スレッドを使用（Firestore gRPCとの相性を考慮）
# 環境変数で調整可能: WEB_CONCURRENCY, GUNICORN_THREADS, GUNICORN_TIMEOUT
CMD ["/bin/sh", "-c", "exec gunicorn --workers ${WEB_CONCURRENCY:-1} --threads ${GUNICORN_THREADS:-8} --bind 0.0.0.0:${PORT:-8080} --timeout ${GUNICORN_TIMEOUT:-45} --graceful-timeout 5 app:app"]