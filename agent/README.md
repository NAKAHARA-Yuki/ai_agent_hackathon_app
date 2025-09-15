# ADK Agent Service (Cloud Run)

このコンテナは ADK の Web/API サーバーを起動します。UI/ゲートウェイとは別コンテナとして Cloud Run にデプロイします。

- Framework: ADK Web/API
- 主要環境変数:
  - GEMINI_API_KEY（自動的に GOOGLE_API_KEY にブリッジ）
  - GEMINI_MODEL（既定: gemini-2.5-pro）
  - MAPS_MCP_ENDPOINT_URL（任意）: Google Maps MCP (Model Context Protocol) HTTP サーバーのツールエンドポイントURL

## ローカル実行（コンテナ）

```
docker build -t agent-service:local agent
docker run --rm -p 8082:8080 \
  -e GEMINI_API_KEY=*** \
  -e GEMINI_MODEL=gemini-2.5-pro \
  agent-service:local
```

- Dev UI: http://localhost:8082
- API も同ポートで提供されます（adk web 既定のエンドポイント構成）。

## エージェント定義

- `agents/travel_planner/agent.py` に `root_agent` を定義し、`agent` として再エクスポートしています（ADK api_server ディレクトリモード対応）。
- `GEMINI_API_KEY` は `GOOGLE_API_KEY` にブリッジされます（追加設定不要）。

### Google Maps MCP (Model Context Protocol) の利用（任意）

このエージェントは `MAPS_MCP_ENDPOINT_URL` が設定されている場合、関数ツール `retrieve_google_maps_platform_docs` を有効化します。

準備:
- 別コンテナや別プロセスで MCP サーバー（`@googlemaps/code-assist-mcp`）を起動。
- そのHTTPツールエンドポイントURLを `MAPS_MCP_ENDPOINT_URL` に設定してください。

例（ローカル）:
- MCP: `npx -y @googlemaps/code-assist-mcp --port 3000`
- 簡易ツールエンドポイント例: `http://localhost:3000/tools/retrieve-google-maps-platform-docs`

使い方:
- ADK Dev UI から `retrieve_google_maps_platform_docs` を選び、クエリを与えると、Maps Platform の最新の公式情報に基づくテキストが返ります。

## 複数エージェントの運用（Cloud Run トポロジ）

- 単一サービスで複数エージェント（親=coordinator + sub_agents）を構成する方法
  - 長所: 運用が簡単、共有状態/文脈の連携が容易
  - 短所: スケール単位は1サービスに集約、障害影響範囲が広がる

- 複数のCloud Runサービスに分割（1サービス=1役割/1エージェント）
  - 長所: スケール/リソース/権限/障害の分離がしやすい
  - 短所: サービス間通信の配線（OIDC等）が必要、管理が増える

まずは単一サービスにまとめ、必要に応じて独立スケールさせたい役割を別サービス化するのがおすすめです。

補足（依存関係の最小化）:
- ランタイムは ADK Web を使用するため、FastAPI/uvicorn/pydantic などの依存は削除しています。
- `requirements.txt` は `google-adk` と `httpx` のみです。

---

**最終更新**: 2025年9月15日
