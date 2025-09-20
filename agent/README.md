# ADK Agent Service - マルチエージェントシステム

Google Agent Development Kit (ADK) 基盤の階層型マルチエージェントシステムです。旅行プランニング専門のAIエージェントとして設計されています。

## 🏗️ エージェントアーキテクチャ

### Root Coordinator Agent
- **役割**: リクエストの振り分け・ルーティング
- **モデル**: Gemini 2.5 Flash Lite（高速判定）
- **機能**: ユーザーリクエストを適切なサブエージェントに振り分け

### サブエージェント構成

#### Travel Planner Agent (`travel_planner/`)
- **役割**: 新規旅行プラン作成
- **モデル**: Gemini 2.5 Pro（高品質生成）
- **機能**: ユーザーの嗜好に基づく詳細な旅行プラン作成

#### Travel Modifier Agent (`travel_modifier/`)
- **役割**: 既存プラン修正・最適化
- **モデル**: Gemini 2.5 Pro
- **機能**: 既存プランの改善提案・カスタマイズ

#### Travel Advisor Agent (`travel_advisor/`)
- **役割**: 当日サポート・リアルタイム対応
- **モデル**: Gemini 2.5 Pro
- **機能**: 旅行中のリアルタイムアドバイス・問題解決

#### Day Advice Agent (`day_advice/`)
- **役割**: 日別詳細アドバイス
- **モデル**: Gemini 2.5 Pro
- **機能**: 各日程の詳細な行動指針・現地情報提供

## 🔧 技術仕様

### フレームワーク・設定
- **ADK**: Google Agent Development Kit
- **API サーバー**: ADK Web/API サーバー
- **デプロイ**: Google Cloud Run
- **ポート**: 8080 (本番) / 8082 (開発)

### 環境変数
```bash
# 必須
GEMINI_API_KEY=***                    # Gemini API キー（自動的に GOOGLE_API_KEY にブリッジ）

# モデル設定
GEMINI_MODEL=gemini-2.5-pro          # 既定: gemini-2.5-flash

# MCP統合（オプション）
MAPS_MCP_ENDPOINT_URL=http://mcp:3000/tools/retrieve-google-maps-platform-docs
```

## 🚀 デプロイメント

### ローカル実行（Docker）
```bash
# イメージビルド
docker build -t agent-service:local agent

# コンテナ実行
docker run --rm -p 8082:8080 \
  -e GEMINI_API_KEY=*** \
  -e GEMINI_MODEL=gemini-2.5-pro \
  agent-service:local
```

**アクセス URL**:
- Dev UI: http://localhost:8082
- API エンドポイント: 同ポート

### Cloud Run デプロイ
```bash
# 本番環境（main ブランチ）
gcloud run deploy travel-agent-service \
  --image gcr.io/PROJECT_ID/agent-service \
  --platform managed \
  --region asia-northeast1 \
  --set-env-vars GEMINI_API_KEY=$GEMINI_API_KEY

# 開発環境（dev ブランチ）
gcloud run deploy travel-agent-service-dev \
  --image gcr.io/PROJECT_ID/agent-service-dev \
  --platform managed \
  --region asia-northeast1 \
  --set-env-vars GEMINI_API_KEY=$GEMINI_API_KEY
```

## 🔌 Google Maps MCP 統合

### MCP (Model Context Protocol) サーバー
このエージェントは `MAPS_MCP_ENDPOINT_URL` が設定されている場合、Google Maps MCP サーバーと連携します。

#### セットアップ
```bash
# MCP サーバー起動
npx -y @googlemaps/code-assist-mcp --port 3000

# エージェントの環境変数
export MAPS_MCP_ENDPOINT_URL="http://localhost:3000/tools/retrieve-google-maps-platform-docs"
```

#### 機能
- **ツール**: `retrieve_google_maps_platform_docs`
- **用途**: Google Maps Platform の最新公式ドキュメント検索
- **利用方法**: ADK Dev UI からツールを選択してクエリ実行

## 🏗️ システムアーキテクチャ

### 階層型マルチエージェント設計
```
Root Coordinator (Gemini 2.5 Flash Lite)
├── Travel Planner (Gemini 2.5 Pro)     # 新規プラン作成
├── Travel Modifier (Gemini 2.5 Pro)    # プラン修正・最適化
├── Travel Advisor (Gemini 2.5 Pro)     # 当日サポート
└── Day Advice (Gemini 2.5 Pro)         # 日別詳細アドバイス
```

### Tool Configuration
- **Primary**: Google Search（主要情報検索）
- **Fallback**: Google Maps MCP（Maps情報補完）
- **競合解決**: 2025年9月修正済み

## ⚠️ 最近の改善・修正 (2025年9月)

### Tool Configuration 競合修正
- Google Search (Primary) + MCP (Fallback) による競合を解決
- Function Tool Import の複数ADKバージョン対応

### Circular Import 問題修正
- Lazy loading パターン導入
- 適切なimport順序の確立

### Model 互換性向上
- **Current**: Gemini 2.5 Pro（ユーザーフィードバック対応）
- **Previous**: Gemini 2.0 Flash Exp（一時的互換性対応）

## 🔧 開発・デバッグ

### ADK エージェント実行
```bash
cd agent
adk api_server --host 0.0.0.0 --port 8082 ./agents
```

### 依存関係
```txt
google-adk        # Agent Development Kit
httpx            # HTTP通信ライブラリ
```

**注意**: ランタイムは ADK Web を使用するため、FastAPI/uvicorn/pydantic などの依存関係は削除済みです。

## 📊 運用・スケーリング

### 単一サービス構成（推奨）
**長所**:
- 運用が簡単
- 共有状態・文脈の連携が容易
- デプロイ・管理の簡素化

**短所**:
- スケール単位が1サービスに集約
- 障害影響範囲が広がる可能性

### 複数サービス分割（将来的）
**長所**:
- スケール・リソース・権限・障害の分離
- エージェント別最適化

**短所**:
- サービス間通信配線（OIDC等）が必要
- 管理複雑性の増加

**推奨アプローチ**: まず単一サービスで開始し、必要に応じて独立スケールが必要な役割を別サービス化
