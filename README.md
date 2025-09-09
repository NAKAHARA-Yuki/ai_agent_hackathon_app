# いざ旅 (Izatabi) - AI Travel Planning App


AIを活用した旅行診断・プランニングアプリケーションです。ユーザーの嗜好や旅行スタイルを診断し、パーソナライズされた国内旅行プランを提案します。

## 🌟 主な機能

- **旅行スタイル診断**: 10の質問でユーザーの旅行嗜好を分析
- **AIペルソナ生成**: 診断結果に基づいた専用AIアシスタントの作成
- **インタラクティブ旅行プランニング**: AIとのチャット形式での旅行計画作成
- **マップ統合**: Google Maps連携による視覚的な旅行ルート表示
- **マルチプラン提案**: 複数の旅行プランの比較・選択機能

## 🏗️ システム構成

### アーキテクチャ概要

```
Frontend (Vue.js) ──→ Backend (Flask) ──→ AI Agent (ADK)
       │                    │                    │
       │                    │                    └──→ Gemini API
       │                    │
       │                    └──→ Firestore Database
       │
       └──→ Google Maps JavaScript API
```

### 各コンポーネント

- **Frontend** (`client/`): Vue.js + Vite による SPA
- **Backend** (`server/`): Python Flask API サーバー
- **AI Agent** (`agent/`): ADK (Agent Development Kit) ベースの AI エージェント
- **MCP Service** (`mcp/`): Google Maps Platform Code Assist MCP サーバー
- **Database**: Google Firestore
- **Deployment**: Google Cloud Run + Docker

### 環境構成

#### 本番環境 (Production)
- **ブランチ**: `main`
- **サービス名**: 
  - `travel-quiz-app`
  - `travel-agent-service`
  - `maps-mcp-service`
- **データベース**: Firestore デフォルトデータベース `(default)`

#### 開発環境 (Development) 
- **ブランチ**: `dev`
- **サービス名**:
  - `travel-quiz-app-dev`
  - `travel-agent-service-dev`
  - `maps-mcp-service-dev`
- **データベース**: Firestore データベース `izatabi-dev`

各環境は独立したGoogle Cloud Runサービスとデータベースを使用し、完全に分離されています。

## 🚀 セットアップ・開発環境構築

### 前提条件

- **Node.js** (18.x以上)
- **Python** (3.9以上) 
- **Docker** & **Docker Compose**
- **Google Cloud CLI** (gcloud)
- **Google Cloud Project** (Firestore、Cloud Run有効化済み)

### 環境変数の設定

#### 1. サーバー環境変数 (`server/.env`)

```bash
# AI/API設定
GEMINI_API_KEY=your_gemini_api_key_here
GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here

# 認証
JWT_SECRET=your_jwt_secret_here

# データベース
GCP_PROJECT_ID=your_project_id
FIRESTORE_DATABASE=(default)  # 本番環境
# FIRESTORE_DATABASE=izatabi-dev  # 開発環境

# 環境設定
FLASK_ENV=development
ENV=development

# エージェント設定
AGENT_BASE_URL=http://localhost:8080
```

#### 2. フロントエンド環境変数 (`client/.env.local`)

```bash
# Google Maps設定
VITE_GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here
VITE_GOOGLE_MAPS_MAP_ID=your_map_id_here
VITE_ENABLE_ADVANCED_MARKER=true
```

### Google Maps の有効化設定

1. **Google Cloud Console** で以下のAPIを有効化:
   - Maps JavaScript API
   - Geocoding API
   - Static Maps API

2. **APIキーの設定**:
   - フロントエンド用: HTTP リファラ制限を設定
   - バックエンド用: IPアドレス制限を設定

3. **Map IDの作成** (Advanced Marker使用時):
   - Google Cloud Console > Maps > Map Management
   - 新しいMap IDを作成し、スタイルを設定

### ローカル開発環境の起動

#### Docker Compose を使用 (推奨)

```bash
# 全サービスを一括起動
docker-compose -f docker-compose.dev.yml up -d

# ログの確認
docker-compose -f docker-compose.dev.yml logs -f
```

#### 個別起動

```bash
# 1. フロントエンド
cd client
npm install
npm run dev  # http://localhost:5173

# 2. バックエンド
cd server
pip install -r requirements.txt
python app.py  # http://localhost:8080


# 3. AIエージェント
cd agent
pip install -r requirements.txt
adk api_server --host 0.0.0.0 --port 8080 ./agents

# 4. MCP サービス (任意)
cd mcp
npm install
npx @googlemaps/code-assist-mcp --port 3000
```

## 📱 使用方法

### 1. 旅行スタイル診断
1. ホーム画面で「診断を始める」をクリック
2. 10個の質問に回答
3. AIが旅行スタイルを分析・ペルソナを生成

### 2. 旅行プラン作成
1. 診断完了後、AIチャット画面に移動
2. 希望や要望をチャットで入力
3. AIが提案する複数のプランから選択
4. マップ上での確認・調整

### 3. プラン管理
- マイページで過去のプラン確認
- プランの編集・削除
- お気に入りの保存

## 🔧 技術仕様

### Frontend (Vue.js)
- **フレームワーク**: Vue 3 + Composition API
- **ビルドツール**: Vite
- **状態管理**: Pinia
- **ルーティング**: Vue Router
- **スタイリング**: CSS Modules
- **チャート**: Chart.js

### Backend (Python Flask)
- **フレームワーク**: Flask
- **認証**: JWT
- **データベースORM**: Google Cloud Firestore SDK
- **API**: RESTful API
- **ログ**: Python logging

### AI Agent (ADK)
- **フレームワーク**: Google Agent Development Kit (ADK)
- **AI Model**: Gemini 2.5 Flash
- **Tools**: Google Search, Maps Platform Code Assist

### インフラ
- **コンテナ**: Docker
- **デプロイ**: Google Cloud Run
- **データベース**: Google Firestore
- **外部API**: Google Maps API, Gemini API

## 🔍 API エンドポイント

### 認証
- `POST /api/auth/signup` - ユーザー登録
- `POST /api/auth/login` - ログイン
- `GET /api/me` - ユーザー情報取得

### 診断・ペルソナ
- `GET /api/questions` - 診断質問の取得
- `POST /api/analyze` - 回答の分析
- `POST /api/persona` - ペルソナ作成
- `GET /api/persona/latest` - 最新ペルソナ取得

### 旅行プラン
- `POST /api/agent/chat` - AIチャット
- `GET /api/plans` - プラン一覧
- `POST /api/plans` - プラン保存
- `GET /api/plans/:id` - プラン詳細
- `DELETE /api/plans/:id` - プラン削除

### 地図・ジオコーディング
- `GET /api/maps-key` - Maps APIキー取得
- `POST /api/geocode` - 地名→座標変換
- `GET /api/maps/static` - 静的地図画像生成

## 🚢 デプロイメント

### Cloud Run デプロイ

```bash
# 1. イメージビルド
docker build -t gcr.io/PROJECT_ID/SERVICE_NAME .

# 2. Container Registry へプッシュ
docker push gcr.io/PROJECT_ID/SERVICE_NAME

# 3. Cloud Run デプロイ
gcloud run deploy SERVICE_NAME \
  --image gcr.io/PROJECT_ID/SERVICE_NAME \
  --platform managed \
  --region asia-northeast1 \
  --allow-unauthenticated
```

### 環境別デプロイ設定

GitHub Actions ワークフローにより自動デプロイ：
- `main`ブランチ → 本番環境
- `dev`ブランチ → 開発環境

## ⚠️ 注意事項

- **APIキーの管理**: 本番環境では環境変数で管理し、ソースコードにコミットしない
- **CORS設定**: 本番環境のドメインに合わせてCORS設定を調整
- **ログレベル**: 本番環境では `LOG_LEVEL=INFO` に設定
- **Firestore Rules**: セキュリティルールを適切に設定

## 🔒 セキュリティ強化

このアプリケーションには包括的なセキュリティ機能が実装されています：

### インフラストラクチャセキュリティ
- **VPCネットワーク分離**: プライベートサブネット、Cloud NAT、ファイアウォールルール
- **IAM最小権限**: サービス専用アカウント、Workload Identity統合
- **Secret Manager**: API キーと機密情報の安全な管理
- **セキュリティ監視**: リアルタイム監視、自動アラート、ログ分析

### アプリケーションセキュリティ  
- **レート制限**: DDoS攻撃対策、API呼び出し制限
- **セキュリティヘッダー**: XSS、CSRF、CSP保護
- **認証強化**: JWT セキュリティ、認証ログ記録
- **脆弱性対策**: コンテナスキャン、セキュリティパターン検出

### セットアップ方法
```bash
# セキュリティインフラの自動セットアップ
cd infrastructure/scripts
export PROJECT_ID="your-gcp-project-id"
export ENVIRONMENT="prod"
./setup-infrastructure.sh

# セキュリティ検証
./validate-security.sh
```

詳細は以下のドキュメントを参照:
- [SECURITY.md](./SECURITY.md) - セキュリティガイド
- [SECURITY_IMPLEMENTATION_GUIDE.md](./SECURITY_IMPLEMENTATION_GUIDE.md) - 実装ガイド
- [infrastructure/README.md](./infrastructure/README.md) - インフラ詳細

## 🛠️ 開発ガイドライン

### ブランチ戦略
- `main`: 本番環境 (stable)
- `dev`: 開発環境 (latest)
- `feature/*`: 機能開発
- `fix/*`: バグ修正

### プルリクエスト
- `dev`ブランチへのPRを作成
- レビュー後、`dev`→`main`へのマージ

### コーディング規約
- **Python**: PEP 8準拠、Black自動フォーマット
- **JavaScript**: ESLint + Prettier
- **コミットメッセージ**: Conventional Commits形式

### Advanced Marker について

バックエンドは `/api/maps-key` でキー・mapId・advanced を返します。MapPanel はこれらを使って JS マップを初期化し、Advanced Marker が有効かつ mapId が指定されている場合のみ高機能ピンを使用します。

注意:
- ルート表示はキー不要の埋め込みを既定で使用します（InvalidKeyMapError 時でも表示可能）
- Advanced Marker を使う場合は、Map ID を設定し、VITE_ENABLE_ADVANCED_MARKER=true にしてください

