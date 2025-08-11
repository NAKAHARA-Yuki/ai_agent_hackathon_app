# ADK Agent Service (Cloud Run)

このコンテナは ADK の Web/API サーバーを起動します。UI/ゲートウェイとは別コンテナとしてCloud Runにデプロイします。

- Framework: ADK Web/API
- 主要環境変数:
  - GEMINI_API_KEY（自動的に GOOGLE_API_KEY にブリッジ）
  - GEMINI_MODEL（既定: gemini-2.0-flash）

## ローカル実行（コンテナ）

```
docker build -t agent-service:local agent
docker run --rm -p 8082:8080 \
  -e GEMINI_API_KEY=*** \
  -e GEMINI_MODEL=gemini-2.0-flash \
  agent-service:local
```

- Dev UI: http://localhost:8082
- API も同ポートで提供されます（adk web 既定のエンドポイント構成）。

## エージェント定義

- `adk_app.py` に `root_agent` を定義（LlmAgent）。
- `GEMINI_API_KEY` は `GOOGLE_API_KEY` にブリッジするため追加設定不要です。

## 複数エージェントの運用（Cloud Run トポロジ）

- 単一サービスで複数エージェント（親=coordinator + sub_agents）を構成する方法
  - 長所: 運用が簡単、共有状態/文脈の連携が容易
  - 短所: スケール単位は1サービスに集約、障害影響範囲が広がる

- 複数のCloud Runサービスに分割（1サービス=1役割/1エージェント）
  - 長所: スケール/リソース/権限/障害の分離がしやすい
  - 短所: サービス間通信の配線（OIDC等）が必要、管理が増える

まずは単一サービスにまとめ、必要に応じて独立スケールさせたい役割を別サービス化するのがおすすめです。
