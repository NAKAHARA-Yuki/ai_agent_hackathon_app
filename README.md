# いざ旅 (Izatabi) - AI Travel Planning App


AIを活用した旅行診断・プランニングアプリケーションです。ユーザーの嗜好や旅行スタイルを診断し、パーソナライズされた国内旅行プランを提案します。

## 🌟 主な機能

- **旅行スタイル診断**: 10の質問でユーザーの旅行嗜好を分析
- **AIペルソナ生成**: 診断結果に基づいた専用AIアシスタントの作成
- **インタラクティブ旅行プランニング**: AIとのチャット形式での旅行計画作成
- **マップ統合**: Google Maps連携による視覚的な旅行ルート表示
- **輸送情報表示**: 移動手段のアイコン・ラベル・所要時間・距離の詳細表示
- **マルチプラン提案**: 複数の旅行プランの比較・選択機能

## 🏗️ システム構成

### アーキテクチャ概要

```
Frontend (Vue.js) ──→ Backend (Flask + Blueprints) ──→ ADK Agent Service ──→ Gemini API
       │                    │                              │                    │
       │                    │ blueprints/                  │                    │
       │                    │ ├── auth.py                  ├──→ Maps MCP ───────┴──→ Maps API
       │                    │ ├── health.py               │    Server
       │                    │ ├── quiz.py                 │
       │                    │ ├── maps.py ─────────────────┤
       │                    │ ├── personas.py             │
       │                    │ ├── plans.py                │
       │                    │ └── ai.py                   │
       │                    │                             │
       │                    └──→ Firestore ──────────────┼──→ Google Cloud
       │                         Database                │
       │                                                 │
       └──→ Google Maps ────────────────────────────────┘
           JavaScript API
```

### 各コンポーネント

- **Frontend** (`client/`): Vue.js + Vite による SPA
- **Backend** (`server/`): Python Flask API サーバー（Flask Blueprint アーキテクチャ）
  - **モジュラー設計**: 7個のBlueprint + 3個のユーティリティモジュール
  - **85.5%の複雑性削減**: 2,686行から388行へのリファクタリング
  - **保守性向上**: 機能別分離、単一責任原則、独立テストが可能
- **ADK Agent Service** (`agent/`): Google ADK ベースのマルチエージェントシステム
  - Root Coordinator Agent（リクエスト振り分け）
  - Travel Planner Agent（新規プラン作成）
  - Travel Advisor Agent（当日サポート）
- **MCP Service** (`mcp/`): MCP (Model Context Protocol) サーバー（Google Maps機能提供）
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

## 📁 ファイル構成

### ディレクトリ構造

```
ai_agent_hackathon_app/
├── client/                 # Vue.js フロントエンド
│   ├── src/
│   │   ├── views/         # ページコンポーネント（15個）
│   │   ├── components/    # 再利用可能なUIコンポーネント（10個）
│   │   ├── services/      # API通信サービス
│   │   ├── stores/        # Pinia状態管理ストア
│   │   ├── router/        # Vue Routerルーティング設定
│   │   ├── assets/        # 静的アセット（画像、CSS等）
│   │   └── constants/     # 定数定義
│   ├── public/            # パブリックアセット
│   ├── index.html         # メインHTMLファイル
│   ├── package.json       # Node.js依存関係
│   ├── jest.config.js     # Jestテスト設定
│   └── vite.config.js     # Viteビルド設定
├── server/                # Flask バックエンド
│   ├── app.py            # メインFlaskアプリケーション（388行、Blueprint統合）
│   ├── blueprints/       # Flask Blueprintモジュール
│   │   ├── auth.py       # 認証エンドポイント（signup, login, profile）
│   │   ├── health.py     # ヘルスチェックエンドポイント
│   │   ├── quiz.py       # 診断質問・分析エンドポイント
│   │   ├── maps.py       # Google Maps統合エンドポイント
│   │   ├── personas.py   # ユーザーペルソナ管理エンドポイント
│   │   ├── plans.py      # 旅行プランCRUD操作エンドポイント
│   │   └── ai.py         # AIエージェントチャット・プラン生成エンドポイント
│   ├── utils/            # ユーティリティモジュール
│   │   ├── auth.py       # JWT・認証ユーティリティ
│   │   ├── data_processing.py # データ正規化・サニタイゼーション
│   │   └── ai_processing.py   # AI処理・テキスト処理ユーティリティ
│   ├── requirements.txt  # Python依存関係
│   ├── pytest.ini       # pytestテスト設定
│   ├── conftest.py       # pytestフィクスチャ定義
│   ├── tests/            # テストスイート
│   └── .env              # 環境変数（要作成）
├── agent/                # ADK マルチエージェントサービス
│   ├── agents/
│   │   └── root_coordinator/
│   │       ├── agent.py     # ルートコーディネーター（リクエスト振り分け）
│   │       ├── travel_planner/
│   │       │   └── agent.py # 旅行プランナーエージェント（新規作成）
│   │       └── travel_advisor/
│   │           └── agent.py # 旅行アドバイザーエージェント（当日サポート）
│   ├── requirements.txt  # ADK依存関係
│   └── Dockerfile        # エージェント用Docker設定
├── mcp/                  # Google Maps MCP サーバー
│   └── Dockerfile        # MCP用Docker設定
├── shared/               # 共有ユーティリティ
│   ├── contracts/        # 型定義・インターフェース
│   └── logging_config.py # ログ設定ユーティリティ
├── Dockerfile            # メインアプリケーション用Docker設定
├── docker-compose.dev.yml # 開発環境Docker Compose
└── .github/workflows/    # CI/CDパイプライン
```

### 主要ファイル詳細

#### フロントエンド（client/src/）

**ビューコンポーネント（views/）** - 15画面
- `StartView.vue` - 診断開始画面（ホーム）
- `InterestsView.vue` - 趣味・興味設定
- `MainView.vue` - メイン画面（診断完了後）
- `QuestionView.vue` - 診断質問画面
- `ResultView.vue` - 診断結果表示
- `MyPageView.vue` - ユーザーマイページ
- `LoginView.vue`、`SignupView.vue` - 認証関連
- `ProcessingView.vue` - 処理中画面
- `TravelPlanWizardView.vue` - 旅行プランウィザード
- `TasksView.vue` - タスク管理
- `PlansListView.vue` - 旅行プラン一覧
- `PlanDetailView.vue` - プラン詳細表示
- `PlanChatView.vue` - AIチャット旅行プランニング
- `TravelDayChatView.vue` - 旅行日チャット

**UIコンポーネント（components/）** - 10個
- `ResultChart.vue` - 診断結果レーダーチャート（Chart.js使用）
- `LoadingScreen.vue` - ローディング画面
- `ProgressBar.vue` - 進捗バー
- `FooterNav.vue` - ボトムナビゲーション
- `Toast.vue` - 通知トースト
- `SessionTimeoutWarning.vue` - セッションタイムアウト警告
- `BackButton.vue` - 戻るボタン
- `DetailScreen.vue` - 詳細画面
- `InputScreen.vue` - 入力画面
- `SuggestionScreen.vue` - 提案画面

**サービス層（services/）**
- `apiClient.js` - バックエンドAPI通信クライアント（axios使用）

**状態管理（stores/）**
- `authStore.js` - 認証状態管理（JWT、ユーザー情報）
- `quizStore.js` - 診断・質問回答状態管理
- `activePlanStore.js` - アクティブな旅行プラン状態管理

#### バックエンド（server/）

**Flask Blueprint アーキテクチャ** - モジュラー設計による85.5%の複雑性削減
- **app.py** (388行) - アプリケーション初期化・Blueprint登録・設定管理
- **blueprints/** - 機能別エンドポイントモジュール（7個のBlueprint）
  - `auth.py` - 認証・ユーザー管理
  - `health.py` - システムヘルスチェック
  - `quiz.py` - 旅行診断・ペルソナ生成
  - `maps.py` - Google Maps API統合
  - `personas.py` - ユーザーペルソナ管理  
  - `plans.py` - 旅行プランCRUD操作
  - `ai.py` - AIエージェントとの統合
- **utils/** - 共有ユーティリティモジュール（3個）
  - `auth.py` - JWT・認証処理
  - `data_processing.py` - データ正規化・サニタイゼーション
  - `ai_processing.py` - AI API呼び出し・テキスト処理

#### AIエージェント（agent/）

**agents/travel_planner/agent.py** - ADK（Agent Development Kit）ベースの旅行計画AI
- Gemini 2.5 Flashモデルを使用
- Google Search、Google Maps MCP ツール統合
- インテリジェントな旅行プラン生成

#### 共有モジュール（shared/）

**contracts/** - フロントエンド・バックエンド間のAPI契約定義
**logging_config.py** - 統一ログ設定（Cloud Logging対応）

## 🔧 主要関数・機能

### バックエンドAPIエンドポイント（Flask Blueprint アーキテクチャ）

#### 認証・ユーザー管理（`server/blueprints/auth.py`）
```python
@auth_bp.route('/api/auth/signup', methods=['POST'])
def signup()
    """新規ユーザー登録、パスワードハッシュ化、JWTトークン生成"""

@auth_bp.route('/api/auth/login', methods=['POST']) 
def login()
    """ログイン認証、JWTトークン発行"""

@auth_bp.route('/api/me', methods=['GET'])
def get_me()
    """認証済みユーザー情報取得"""

@auth_bp.route('/api/profile', methods=['GET', 'POST'])
def profile()
    """ユーザープロフィール取得・更新"""
```

#### 旅行診断・ペルソナ（`server/blueprints/quiz.py`, `server/blueprints/personas.py`）
```python
@quiz_bp.route('/api/questions')
def get_questions()
    """10個の旅行診断質問データ取得"""

@quiz_bp.route('/api/analyze', methods=['POST'])
def analyze_responses()
    """診断回答を分析し、8次元スコア算出"""

@personas_bp.route('/api/persona', methods=['POST'])
def create_persona()
    """診断結果からAIペルソナ生成（Gemini API使用）"""

@personas_bp.route('/api/persona/latest', methods=['GET'])
def get_latest_persona()
    """最新のペルソナ情報取得"""
```

#### AIチャット・旅行プランニング（`server/blueprints/ai.py`, `server/blueprints/plans.py`）
```python
@ai_bp.post('/api/agent/chat')
def chat_with_agent()
    """AIエージェントとのチャット、旅行プラン提案"""

@ai_bp.route('/api/generate_plan', methods=['POST'])
def generate_travel_plan()
    """旅行プラン生成（Gemini API直接呼び出し）"""

@plans_bp.route('/api/plans', methods=['GET', 'POST'])
def handle_plans()
    """旅行プラン一覧取得・新規作成"""

@plans_bp.route('/api/plans/<plan_id>', methods=['GET', 'DELETE'])
def handle_plan(plan_id)
    """特定プランの詳細取得・削除"""

@plans_bp.route('/api/active-plan', methods=['GET', 'POST'])
def handle_active_plan()
    """アクティブプラン取得・設定"""
```

#### Google Maps統合（`server/blueprints/maps.py`）
```python
@maps_bp.get('/api/maps-key')
def get_maps_js_key()
    """フロントエンド用Google Maps APIキー・設定提供"""

@maps_bp.post('/api/geocode')
def geocode_location()
    """地名から緯度経度への変換（Geocoding API）"""

@maps_bp.get('/api/maps/static')
def generate_static_map()
    """静的地図画像生成"""
```

#### ユーティリティ関数（`server/utils/`）
```python
# server/utils/data_processing.py
def _normalize_places_list(raw)
    """AIレスポンスから場所リストを正規化"""

def _normalize_route_info(obj)
    """ルート情報の正規化"""

def _extract_trailing_json(s)
    """AIレスポンスからJSON構造データ抽出"""

# server/utils/ai_processing.py
def retry_on_503(func, max_retries=3)
    """503エラー時のリトライ機能"""

# server/utils/auth.py
# JWT認証・トークン処理ユーティリティ
```

### フロントエンド主要機能

#### API通信（services/apiClient.js）
```javascript
// 認証付きHTTPクライアント（axios使用）
// 自動JWTヘッダー付与、レスポンス/エラーハンドリング
// 全APIエンドポイントへの型安全アクセス
```

#### 状態管理ストア

**authStore.js（Pinia）**
```javascript
// ユーザー認証状態管理
// - login/logout機能
// - JWTトークン管理
// - セッション自動更新
// - ページリロード時状態復元
```

**quizStore.js（Pinia）**
```javascript  
// 診断・質問回答管理
// - 質問進捗追跡
// - 回答データ保存
// - スコア計算結果保持
// - ペルソナ情報管理
```

**activePlanStore.js（Pinia）**
```javascript
// アクティブ旅行プラン管理
// - 現在の計画状態
// - チャット履歴
// - マップ表示状態
```

#### 主要UIコンポーネント

**ResultChart.vue**
- Chart.js レーダーチャート
- 8次元診断結果視覚化
- アニメーション効果
- レスポンシブデザイン

**その他UIコンポーネント**
- `LoadingScreen.vue` - アプリケーション全体のローディング表示
- `ProgressBar.vue` - 診断進捗表示
- `FooterNav.vue` - ボトムナビゲーション
- `Toast.vue` - 通知メッセージ表示
- `SessionTimeoutWarning.vue` - セッション期限警告
- `BackButton.vue` - 共通戻るボタン
- `DetailScreen.vue`、`InputScreen.vue`、`SuggestionScreen.vue` - 各種画面コンポーネント

### AIエージェント機能（ADK統合）

#### エージェントアーキテクチャ

本アプリケーションは **Google Agent Development Kit (ADK)** を使用した階層型マルチエージェントシステムを採用しています：

```
Root Coordinator Agent (ルートコーディネーター)
├── Travel Planner Agent (旅行プランナー)
│   └── 新規旅行プラン作成・3案提案・JSON構造化出力
└── Travel Advisor Agent (旅行アドバイザー)
    └── 当日サポート・既存プラン調整・リアルタイム対応
```

#### エージェント詳細仕様

**1. Root Coordinator Agent** (`agents/root_coordinator/agent.py`)
- **役割**: ユーザーリクエストの分析・適切なサブエージェントへの振り分け
- **モデル**: `gemini-2.5-flash-lite`
- **判断基準**:
  - 新規旅行プラン作成依頼 → Travel Planner
  - 既存プラン修正・当日対応 → Travel Advisor
- **特徴**: サブエージェントの応答をそのまま返す（形式変更なし）

**2. Travel Planner Agent** (`agents/root_coordinator/travel_planner/agent.py`)
- **役割**: persona/profile情報から3つの完全な旅行プランを生成
- **モデル**: `gemini-2.5-pro`
- **出力形式**: 厳密なJSON構造（plans配列、itinerary、places、route_info含む）
- **ツール統合**: MCP (Model Context Protocol) による Google Maps機能統合
- **特徴**:
  - 地理的合理性・季節感・移動時間を考慮
  - 輸送手段（transport）詳細情報付与
  - 危険/非現実/閉鎖施設の除外

**3. Travel Advisor Agent** (`agents/root_coordinator/travel_advisor/agent.py`)
- **役割**: 旅行当日のリアルタイムサポート・既存プラン調整
- **モデル**: `gemini-2.5-pro`
- **対応シナリオ**:
  - 天候変化による代替案提案
  - 交通遅延時の時間調整
  - 現在地からの最適ルート案内
  - 営業時間・混雑状況確認
  - 緊急時サポート情報
- **出力形式**: JSON構造（suggestions、updated_schedule、route_info含む）

#### ADK技術統合詳細

**Agent Development Kit (ADK) 基盤**
```python
# エージェント定義パターン
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset

agent = LlmAgent(
    name="agent_name",
    model="gemini-2.5-pro",
    description="Agent description",
    instruction="Detailed instructions...",
    sub_agents=[...],  # サブエージェント配列
    tools=[...]        # ツールセット
)
```

**MCP (Model Context Protocol) ツール統合**
- **Google Maps MCP**: 地図データ・経路情報・場所検索（MCP経由）
- **接続方式**: StdioConnectionParams経由でnpxプロセス起動
- **API Key管理**: 環境変数`GOOGLE_MAPS_API_KEY`から自動設定
- **タイムアウト**: 10秒（設定可能）

#### エージェント通信プロトコル

**ADK API Server 呼び出しフロー**
1. **セッション作成**: `POST /apps/{app_name}/users/{user_id}/sessions/{session_id}`
2. **エージェント実行**: `POST /run` with payload
3. **応答処理**: events配列からmodel応答を抽出

**Flask統合エンドポイント** (`server/blueprints/ai.py`)
```python
@ai_bp.post('/api/agent/chat')
def agent_chat():
    # 1. ユーザー認証確認
    # 2. エージェントサービス可用性チェック
    # 3. ADK呼び出し（call_adk_agent_chat）
    # 4. 構造化データ抽出・正規化
    # 5. Geminiフォールバック（エージェント不可時）
```

#### エージェント設定・デプロイメント

**環境変数設定**
```bash
# エージェント基本設定
AGENT_BASE_URL=http://localhost:8080          # ADK API Server URL
AGENT_API_KEY=optional_bearer_token           # 認証トークン（任意）
AGENT_HTTP_TIMEOUT=180                        # HTTPタイムアウト（秒）

# AIモデル設定
GEMINI_API_KEY=your_gemini_api_key           # Gemini API認証
GEMINI_MODEL=gemini-2.5-pro                 # 使用モデル指定

# MCP設定
GOOGLE_MAPS_API_KEY=your_maps_api_key        # Maps MCP用
MAPS_MCP_ENDPOINT_URL=http://mcp:3000/tools/retrieve-google-maps-platform-docs
```

**Docker Compose設定** (`docker-compose.dev.yml`)
```yaml
services:
  agent-service:
    build: ./agent
    ports:
      - "8082:8080"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - GOOGLE_MAPS_API_KEY=${GOOGLE_MAPS_API_KEY}
  
  mcp-service:
    build: ./mcp
    ports:
      - "3000:3000"
    command: npx @googlemaps/code-assist-mcp --port 3000
```

#### エージェント品質保証

**JSON応答検証**
- **カウンター管理**: `app.AGENT_JSON_OK` / `app.AGENT_JSON_FAIL`
- **構造検証**: plans配列、itinerary形式、places座標
- **エラーハンドリング**: 503エラー指数バックオフリトライ

**ログ・監視**
- **トレースID**: リクエスト追跡用ユニークID付与
- **レスポンス時間**: ミリ秒単位パフォーマンス計測
- **ペイロードログ**: デバッグ用詳細ログ（設定可能）

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
AGENT_BASE_URL=http://localhost:8082
MAPS_MCP_ENDPOINT_URL=http://localhost:3000/tools/retrieve-google-maps-platform-docs
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

# 2. バックエンド（Flask Blueprint アーキテクチャ）
cd server
pip install -r requirements.txt
python app.py  # http://localhost:8080
# Flask Blueprintによりモジュラー化されたAPI（7個のBlueprint統合）

# 3. ADKエージェントサービス
cd agent
pip install -r requirements.txt
adk api_server --host 0.0.0.0 --port 8082 ./agents

# 4. MCP サービス (任意)
cd mcp
npm install
npx @googlemaps/code-assist-mcp --port 3000
```

### テスト実行

```bash
# フロントエンドテスト
cd client
npm test                    # 全テスト実行
npm run test:coverage      # カバレッジ付き実行
npm test -- --watch        # 監視モード

# バックエンドテスト（Flask Blueprint アーキテクチャ）
cd server
pip install -r requirements.txt  # テスト依存関係のインストールが必要
pytest                     # 全テスト実行（Blueprint統合後の構造をテスト）
pytest --cov=app          # カバレッジ付き実行
pytest -v                 # 詳細出力
```

> **注意**: テストを実行するには、依存関係のインストールと適切な環境設定が必要です。詳細は [テスト関連ドキュメント](docs/testing/) を参照してください。

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
- **フレームワーク**: Vue 3.4.21 + Composition API
- **ビルドツール**: Vite 5.2.8
- **状態管理**: Pinia
- **ルーティング**: Vue Router
- **スタイリング**: CSS Modules
- **チャート**: Chart.js 4.5.0
- **テスト**: Jest 29.7.0

### Backend (Python Flask)
- **フレームワーク**: Flask 3.0.3 + Blueprint アーキテクチャ
- **認証**: JWT (PyJWT 2.8.0)
- **データベースORM**: Google Cloud Firestore SDK 2.16.0
- **AI**: Google Generative AI 0.7.1
- **API**: RESTful API（7個のBlueprint + 3個のユーティリティモジュール）
- **ログ**: Python logging
- **デプロイ**: Gunicorn 22.0.0
- **テスト**: pytest 7.4.4（47+ テストケース、完全カバレッジ）
- **アーキテクチャ**: モジュラー設計（85.5%の複雑性削減）

### ADK Agent Service (Multi-Agent)
- **フレームワーク**: Google Agent Development Kit (ADK)
- **AI Models**: 
  - Root Coordinator: Gemini 2.5 Flash Lite (高速ルーティング)
  - Travel Planner: Gemini 2.5 Pro (高品質プラン生成)
  - Travel Advisor: Gemini 2.5 Pro (詳細サポート)
- **Tools**: Google Maps MCP (Model Context Protocol), Google Search
- **Architecture**: 階層型マルチエージェント（ルートコーディネーター + サブエージェント）
- **Communication**: ADK API Server プロトコル

### インフラ
- **コンテナ**: Docker
- **デプロイ**: Google Cloud Run
- **データベース**: Google Firestore
- **外部API**: Google Maps API, Gemini API

### テスト・品質保証
- **Frontend**: Jest 29.7.0 + @vue/test-utils
- **Backend**: pytest 7.4.4 + pytest-flask
- **カバレッジ**: C1カバレッジ100%目標
- **テスト項目**: 130+ 包括的テストケース
- **CI/CD**: GitHub Actions 自動テスト実行

## 📚 ドキュメント

本プロジェクトは包括的なドキュメントを提供しています：

### 主要ドキュメント
- **README.md** (本ファイル) - プロジェクト全体の概要・セットアップ・使用方法
- **[docs/](docs/)** - 詳細ドキュメント集

### 詳細ドキュメント (`docs/` ディレクトリ)
- **[AIエージェント実装](docs/AGENT_IMPLEMENTATION.md)** - ADK統合・マルチエージェントシステム詳細仕様
- **[テスト関連](docs/testing/)** - テストスイート実装サマリー・設計書
- **[保守関連](docs/maintenance/)** - 未使用ファイル整理レポート等

### コンポーネント別ドキュメント
- **agent/README.md** - ADKエージェントサービスの詳細
- **agent/AGENT_FIX_NOTES.md** - エージェント設定修正履歴
- **agent/tools/README.md** - エージェントツール説明

### 開発・保守用ドキュメント
- **.github/copilot-instructions.md** - 開発者向け詳細手順書・トラブルシューティング

## 🔍 API エンドポイント

### システム・設定
- `GET /api/health` - システムヘルスチェック
- `GET /api/maps-key` - Maps API設定取得

### 認証
- `POST /api/auth/signup` - ユーザー登録
- `POST /api/auth/login` - ログイン
- `GET /api/me` - ユーザー情報取得
- `GET /api/profile` - プロフィール取得
- `POST /api/profile` - プロフィール更新

### 診断・ペルソナ
- `GET /api/questions` - 診断質問の取得
- `GET /api/hobbies` - 趣味マスターデータ取得
- `POST /api/analyze` - 回答の分析
- `POST /api/persona` - ペルソナ作成
- `GET /api/persona/latest` - 最新ペルソナ取得

### 旅行プラン・AI機能
- `POST /api/agent/chat` - **ADKエージェントチャット** (メイン機能)
  - **リクエスト**: `{ "message": string, "session_id": string }`
  - **レスポンス**: 構造化JSON（plans, suggestions, itinerary, route_info含む）
  - **フォールバック**: エージェント不可時Gemini API直接呼び出し
- `POST /api/generate_plan` - Gemini旅行プラン生成（エージェント補助機能）
- `GET /api/plans` - プラン一覧
- `POST /api/plans` - プラン保存
- `GET /api/plans/:id` - プラン詳細
- `DELETE /api/plans/:id` - プラン削除
- `GET /api/active-plan` - アクティブプラン取得
- `POST /api/active-plan` - アクティブプラン設定

### 地図・ジオコーディング
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

## 📄 ライセンス

このプロジェクトは著作権で保護されています。

**Copyright (c) 2025 NAKAHARA-Yuki. All rights reserved.**

このソフトウェアの使用、複製、配布、修正、またはその他の利用には、著作権者の事前の書面による許可が必要です。詳細については、[LICENSE](LICENSE) ファイルをご確認ください。

ライセンスに関するお問い合わせは、プロジェクト所有者までご連絡ください。

---

## 📝 更新履歴

### 最新更新 (2025年9月)
- ✅ **Flask Blueprint リファクタリング**: 2,686行のapp.pyを388行に削減、7個のBlueprintと3個のユーティリティモジュールに分割
- ✅ **エージェント実装ドキュメント化**: ADK統合・マルチエージェント詳細仕様書
- ✅ 輸送情報表示機能の追加（移動手段のアイコン・ラベル・所要時間・距離）
- ✅ ドキュメント構造の整理・統合
- ✅ コンポーネント情報の正確性向上
- ✅ API エンドポイント一覧の完全化
- ✅ テスト関連ドキュメントの体系化
- ✅ 未使用ファイルの削除・整理

### 主要機能実装完了
- ✅ Vue.js 3.4.21 フロントエンド
- ✅ Flask 3.0.3 バックエンド  
- ✅ Google ADK エージェント統合
- ✅ 包括的テストスイート (163+ テストケース)
- ✅ Google Cloud Run デプロイメント対応

