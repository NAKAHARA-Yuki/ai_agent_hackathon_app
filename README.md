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
│   ├── app.py            # メインFlaskアプリケーション
│   ├── requirements.txt  # Python依存関係
│   ├── pytest.ini       # pytestテスト設定
│   ├── conftest.py       # pytestフィクスチャ定義
│   ├── tests/            # テストスイート
│   └── .env              # 環境変数（要作成）
├── agent/                # AI エージェントサービス
│   ├── agents/
│   │   └── travel_planner/
│   │       ├── __init__.py
│   │       └── agent.py  # メインADKエージェント実装
│   ├── tools/            # エージェント用ツール
│   ├── requirements.txt  # Python ADK依存関係
│   └── Dockerfile        # エージェント用Docker設定
├── mcp/                  # Maps Code Assist MCP サーバー
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

**app.py** - メインFlaskアプリケーション（2,700+行）
主要な機能群：
- 認証・ユーザー管理
- 旅行診断・ペルソナ生成
- AIエージェントとの統合
- Google Maps API統合
- 旅行プラン管理
- データベース操作（Firestore）

#### AIエージェント（agent/）

**agents/travel_planner/agent.py** - ADK（Agent Development Kit）ベースの旅行計画AI
- Gemini 2.5 Flashモデルを使用
- Google Search、Maps Platform Code Assistツール統合
- インテリジェントな旅行プラン生成

#### 共有モジュール（shared/）

**contracts/** - フロントエンド・バックエンド間のAPI契約定義
**logging_config.py** - 統一ログ設定（Cloud Logging対応）

## 🔧 主要関数・機能

### バックエンドAPIエンドポイント（server/app.py）

#### 認証・ユーザー管理
```python
@app.route('/api/auth/signup', methods=['POST'])
def signup()
    """新規ユーザー登録、パスワードハッシュ化、JWTトークン生成"""

@app.route('/api/auth/login', methods=['POST']) 
def login()
    """ログイン認証、JWTトークン発行"""

@app.route('/api/me', methods=['GET'])
def get_me()
    """認証済みユーザー情報取得"""

@app.route('/api/profile', methods=['GET', 'POST'])
def profile()
    """ユーザープロフィール取得・更新"""
```

#### 旅行診断・ペルソナ
```python
@app.route('/api/questions')
def get_questions()
    """10個の旅行診断質問データ取得"""

@app.route('/api/analyze', methods=['POST'])
def analyze_responses()
    """診断回答を分析し、8次元スコア算出"""

@app.route('/api/persona', methods=['POST'])
def create_persona()
    """診断結果からAIペルソナ生成（Gemini API使用）"""

@app.route('/api/persona/latest', methods=['GET'])
def get_latest_persona()
    """最新のペルソナ情報取得"""
```

#### AIチャット・旅行プランニング
```python
@app.post('/api/agent/chat')
def chat_with_agent()
    """AIエージェントとのチャット、旅行プラン提案"""

@app.route('/api/generate_plan', methods=['POST'])
def generate_travel_plan()
    """旅行プラン生成（Gemini API直接呼び出し）"""
```

#### 旅行プラン管理
```python
@app.route('/api/plans', methods=['GET', 'POST'])
def handle_plans()
    """旅行プラン一覧取得・新規作成"""

@app.route('/api/plans/<plan_id>', methods=['GET', 'DELETE'])
def handle_plan(plan_id)
    """特定プランの詳細取得・削除"""

@app.route('/api/active-plan', methods=['GET', 'POST'])
def handle_active_plan()
    """アクティブプラン取得・設定"""
```

#### Google Maps統合
```python
@app.get('/api/maps-key')
def get_maps_js_key()
    """フロントエンド用Google Maps APIキー・設定提供"""

@app.post('/api/geocode')
def geocode_location()
    """地名から緯度経度への変換（Geocoding API）"""

@app.get('/api/maps/static')
def generate_static_map()
    """静的地図画像生成"""
```

#### ユーティリティ関数
```python
def _normalize_places_list(raw)
    """AIレスポンスから場所リストを正規化"""

def _normalize_route_info(obj)
    """ルート情報の正規化"""

def _extract_trailing_json(s)
    """AIレスポンスからJSON構造データ抽出"""

def retry_on_503(func, max_retries=3)
    """503エラー時のリトライ機能"""
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

### AIエージェント機能（agent/agents/travel_planner/agent.py）

```python
# ADKベースの旅行計画エージェント
# - Gemini 2.5 Flash モデル統合
# - Google Search ツール
# - Maps Platform Code Assist ツール
# - コンテキスト保持チャット
# - 構造化旅行プラン生成
```

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

### テスト実行

```bash
# フロントエンドテスト
cd client
npm test                    # 全テスト実行
npm run test:coverage      # カバレッジ付き実行
npm test -- --watch        # 監視モード

# バックエンドテスト
cd server
pip install -r requirements.txt  # テスト依存関係のインストールが必要
pytest                     # 全テスト実行
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
- **フレームワーク**: Flask 3.0.3
- **認証**: JWT (PyJWT 2.8.0)
- **データベースORM**: Google Cloud Firestore SDK 2.16.0
- **AI**: Google Generative AI 0.7.1
- **API**: RESTful API
- **ログ**: Python logging
- **デプロイ**: Gunicorn 22.0.0
- **テスト**: pytest 7.4.4

### AI Agent (ADK)
- **フレームワーク**: Google Agent Development Kit (ADK)
- **AI Model**: Gemini 2.5 Pro
- **Tools**: Google Search, Maps Platform Code Assist

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
- `POST /api/agent/chat` - AIエージェントチャット
- `POST /api/generate_plan` - 旅行プラン生成
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
- ✅ ドキュメント構造の整理・統合
- ✅ コンポーネント情報の正確性向上
- ✅ API エンドポイント一覧の完全化
- ✅ テスト関連ドキュメントの体系化
- ✅ 未使用ファイルの削除・整理

### 主要機能実装完了
- ✅ Vue.js 3.4.21 フロントエンド
- ✅ Flask 3.0.3 バックエンド  
- ✅ Google ADK エージェント統合
- ✅ 包括的テストスイート (130+ テストケース)
- ✅ Google Cloud Run デプロイメント対応

