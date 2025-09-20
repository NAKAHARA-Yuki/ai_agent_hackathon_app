# AI エージェント ハッカソン 旅行アプリ

Vue.js フロントエンド、Flask バックエンド、Google ADK エージェントサービス、Google Maps MCP サーバーを使用した AI 搭載旅行計画アプリケーション。Google Maps と Gemini AI 統合で Docker + Cloud Run 経由でデプロイされます。

**ここにない情報に遭遇した場合のみ、常にこれらの手順を最初に参照し、検索やbashコマンドにフォールバックしてください。**

## 効果的な作業方法

**重要 - ビルドや長時間実行コマンドを決してキャンセルしないでください。適切なタイムアウトを常に使用してください。**

### リポジトリのブートストラップ、ビルド、テスト

**クライアント (Vue.js + Vite):**
```bash
cd client
npm install                    # 約8秒かかります
npm run build                  # 約3秒かかります  
npm run dev                    # 約300msでデベロッパーサーバーが開始します
```
- タイムアウト: npm install は60秒以上、ビルドは30秒以上を使用
- キャンセル禁止: すべてのnpm操作は適切な時間内に完了します

**サーバー (Flask + Python):**
```bash
cd server
pip install -r requirements.txt  # 約25秒かかります、SSL警告が予想されます
```
- タイムアウト: 大きな依存関係ツリーのため、pip installは120秒以上を使用
- キャンセル禁止: 依存関係にはGoogle Cloudライブラリが含まれており大きいです
- **予想される警告**: SSL証明書警告と非推奨通知は正常です

**エージェント (Google ADK):**
```bash
cd agent  
pip install -r requirements.txt  # ファイアウォール/ネットワーク制限により失敗する可能性があります
```
- **既知の問題**: ネットワーク制限によりエージェント依存関係のインストールがよく失敗します
- サンドボックス環境では予想される失敗として文書化
- 適切なネットワーキングを持つ実際のGoogle Cloud環境では動作します

**MCP (Google Maps MCP):**
```bash
npx -y @googlemaps/code-assist-mcp --port 3000  # MCPサーバーをインストールして実行
```
- タイムアウト: 初回実行時（パッケージダウンロード）は60秒以上を使用

### 開発モード検証

**バックエンドサーバーの開始:**
```bash
cd server
FLASK_ENV=development JWT_SECRET=dev-secret-change-me python3 app.py
```
- サーバーは http://localhost:8080 で開始します
- パスワード 'password' のダミーユーザー 'devuser' を作成します  
- Firestoreが利用できない場合はDevDB（インメモリ）を使用します
- DBセットアップで初期化に約15秒かかります

**フロントエンドの開始:**
```bash
cd client
npm run dev  # http://localhost:5173/ で開始します
```
- localhost:8080へのAPI呼び出しをプロキシします（vite.config.jsで設定）
- 即座に開始します（約300ms）

**ヘルスチェック検証:**
```bash
curl http://localhost:8080/api/health
```
期待される応答: `{"status": "ok", "env": "development", "db": "devdb", ...}`

### Docker ビルド (本番環境)

**メインアプリケーション:**
```bash
docker build -t travel-app .  # 5-15分かかります。決してキャンセルしないでください。
```
- タイムアウト: 完全なビルドには900秒以上（15分以上）を使用
- **既知の問題**: SSL証明書制限によりサンドボックス環境では失敗する可能性があります
- 適切なDockerレジストリアクセスを持つ本番環境では動作します

**個別コンポーネントビルド:**
```bash
cd agent && docker build -t agent-service .     # ADKエージェント用
cd mcp && docker build -t mcp-service .         # MCPサーバー用  
```

**Docker Compose (開発環境):**
```bash
# server/.envファイルに適切なAPIキーが必要です
docker compose -f docker-compose.dev.yml up
```
- **前提条件**: 必要な環境変数を含む `server/.env` を作成
- **既知の問題**: 適切な.env設定なしでは失敗します

## 検証シナリオ

**これらの完全なエンドツーエンドシナリオを通じて常に手動で変更を検証してください:**

### 開発ワークフロー検証
1. **ビルド検証**: クライアントビルドを実行し、`dist/`フォルダーが作成されることを確認
2. **サーバーヘルス**: サーバーを開始し、`/api/health`が200 OKを返すことを確認
3. **フロントエンド接続**: クライアントデベロッパーサーバーとバックエンドの両方を開始し、プロキシが動作することを確認
4. **APIエンドポイント**: `/api/questions`、`/api/hobbies`などの主要エンドポイントをテスト
5. **テストスイート実行**: 163+ テストケース（フロントエンド81個、バックエンド82個）が全て成功することを確認

### 本番デプロイメント検証  
1. **Dockerビルド**: マルチステージビルドが成功することを確認
2. **コンテナ開始**: ビルドされたイメージがエラーなく開始することを確認
3. **ヘルスエンドポイント**: コンテナがヘルスチェックに応答することを確認
4. **静的アセット**: SPAフォールバックがフロントエンドを正しく提供することを確認

### ユーザージャーニー検証
1. **登録/ログイン**: アカウント作成、JWTトークン生成を確認
2. **旅行クイズ**: 性格評価を完了  
3. **AI計画**: 旅行プランを生成（APIキーが必要）
4. **マップ統合**: Google Maps機能を確認（Maps APIキーが必要）

## 環境要件

### 必要な環境変数（本番環境）
```bash
# コアAPIキー
GEMINI_API_KEY=your_gemini_api_key           # AI機能に必要
GOOGLE_MAPS_API_KEY=your_maps_api_key        # Maps統合に必要
JWT_SECRET=your_jwt_secret                   # 認証に必要

# Google Cloud（本番環境）
GCP_PROJECT_ID=your_project_id               # Firestore用
GOOGLE_CLOUD_PROJECT=your_project_id         # 代替名

# クライアント環境（Vite）
VITE_GOOGLE_MAPS_API_KEY=your_public_api_key # パブリックMaps APIキー
VITE_GOOGLE_MAPS_MAP_ID=your_map_id          # Advanced Markers用（オプション）
VITE_ENABLE_ADVANCED_MARKER=true             # 高度な機能（オプション）

# エージェントサービス
AGENT_BASE_URL=http://localhost:8080         # ADKエージェントエンドポイント
MAPS_MCP_ENDPOINT_URL=http://mcp:3000/tools/retrieve-google-maps-platform-docs
```

### 開発フォールバック
- **APIキーなし**: サーバーはダミーデータを使用し、ログに警告を表示
- **Firestoreなし**: DevDB（インメモリ）が自動的に使用されます  
- **エージェントなし**: 直接Gemini API呼び出しにフォールバック
- **開発モード**: より高速な反復のために認証要件をバイパス

## 主要コンポーネントと構造

### フロントエンド (`client/`)
- **フレームワーク**: Vue.js 3.4.21 + Vite 5.2.8
- **主要依存関係**: chart.js、vue-router、pinia
- **ビルド出力**: `dist/`（本番環境でFlaskが提供）
- **デベロッパーサーバー**: APIプロキシ付きhttp://localhost:5173

### バックエンド (`server/`)  
- **フレームワーク**: Flask 3.0.3 + Gunicorn + Flask Blueprint アーキテクチャ
- **データベース**: Google Cloud Firestore（本番） / DevDB（開発）
- **API**: 8個のBlueprint（auth, health, quiz, maps, personas, plans, ai, memories）
- **主要機能**: JWT認証、AI分析、旅行プラン生成、Veo動画生成、思い出管理

### エージェントサービス (`agent/`)
- **フレームワーク**: Google ADK（Agent Development Kit）マルチエージェントシステム
- **目的**: Gemini AIを使用したインテリジェント旅行計画
- **構成**: Root Coordinator + 4サブエージェント（Travel Planner, Travel Modifier, Travel Advisor, Day Advice）
- **依存関係**: httpx、google-adk（制限された環境では失敗する可能性）
- **エンドポイント**: 旅行プラン生成、修正、アドバイス用API

### MCPサーバー (`mcp/`)
- **目的**: MCP (Model Context Protocol) サーバー（Google Maps機能提供）
- **ランタイム**: @googlemaps/code-assist-mcpを使用したNode.js
- **エンドポイント**: `/tools/retrieve-google-maps-platform-docs`

### デプロイメント (`Dockerfile` + Cloud Run)
- **マルチステージ**: Node.jsビルド → Pythonランタイム
- **プロセス**: フロントエンドビルド → Flaskスタティックにコピー → gunicorn実行
- **ポート**: 8080（PORT環境変数で設定可能）

## 一般的なタスクとトラブルシューティング

### ビルドの問題
- **npm installの警告**: 正常です。エラーがなければ続行してください
- **pip SSL警告**: サンドボックス環境では予想されます  
- **エージェントインストール失敗**: ネットワーク制限として文書化、クラウドでは動作します
- **Dockerビルド失敗**: サンドボックスでSSL証明書の問題、本番環境では動作します

### ランタイムの問題
- **サーバーが開始しない**: 本番モードでJWT_SECRETを確認
- **AI応答なし**: GEMINI_API_KEYが設定されていることを確認
- **マップが読み込まれない**: VITE_GOOGLE_MAPS_API_KEYを確認
- **認証失敗**: JWT_SECRETとユーザー作成を確認

### テストコマンド
```bash
# コア機能の迅速な検証
cd server && python3 -c "
import app
with app.app.test_client() as client:
    print('Health:', client.get('/api/health').get_json())"

# クライアントビルドアーティファクトを確認
cd client && npm run build && ls -la dist/

# サーバーエンドポイントの応答を確認
curl -f http://localhost:8080/api/questions || echo "Server not running"
```

### パフォーマンスノート
- **クライアントビルド**: 合計約10秒（インストール + ビルド）
- **サーバー起動**: データベース初期化で約15秒  
- **Dockerビルド**: ネットワークとキャッシュに応じて5-15分
- **MCP初回実行**: パッケージダウンロードで約60秒

## 追加コンテキスト

### リポジトリ構造
```
.
├── client/          # Vue.jsフロントエンド
├── server/          # Flaskバックエンド  
├── agent/           # Google ADKエージェントサービス
├── mcp/             # Google Maps MCPサーバー
├── shared/          # 共有コントラクト/タイプ
├── Dockerfile       # マルチステージ本番ビルド
└── docker-compose.dev.yml  # 開発オーケストレーション
```

### CI/CDパイプライン (`.github/workflows/deploy-cloud-run.yml`)
- **トリガー**: mainブランチへのプッシュ
- **プロセス**: エージェント+MCPビルド → Cloud Runにデプロイ → メインアプリビルド+デプロイ
- **依存関係**: Google Cloud認証情報、Artifact Registry

### 主要URLとエンドポイント
- **開発フロントエンド**: http://localhost:5173  
- **開発バックエンド**: http://localhost:8080
- **ヘルスチェック**: `/api/health`
- **認証**: `/api/auth/login`、`/api/auth/signup`
- **旅行計画**: `/api/agent/chat`、`/api/generate_plan`
- **マップ統合**: `/api/maps-key`、`/api/geocode`

**注意**: 常にビルドを完了まで実行し、適切なタイムアウトを使用し、完全なユーザーシナリオを通じて機能を検証してください。アプリケーションは外部サービスが利用できない場合に適切に劣化するように設計されています。

## 最新の改善・修正点

### Flask Blueprint リファクタリング (2025年9月-2025年1月)
- **2,686行のapp.py → 388行に削減** (85.5%の複雑性削減)
- **8個のBlueprint**: auth, health, quiz, maps, personas, plans, ai, memories
- **3個のユーティリティモジュール**: utils/auth.py, utils/data_processing.py, utils/ai_processing.py
- **保守性向上**: 機能別分離、単一責任原則、独立テストが可能

### ADK エージェント設定修正
- **Tool Configuration 競合解決**: Google Search (Primary) + MCP (Fallback)
- **Circular Import 修正**: Lazy loading、適切なimport順序
- **Model 互換性**: Gemini 2.5 Pro 使用、FunctionTool 互換性向上
- **Agent Structure**: Root Coordinator + Sub-Agents (Travel Planner, Travel Advisor)

### 包括的テストスイート実装
- **163+ テストケース**: フロントエンド81個、バックエンド82個
- **C1カバレッジ100%目標**: Jest + pytest による完全カバレッジ
- **テスト技術**: Mock/Real API両対応、エラーハンドリング、境界値テスト
- **CI/CD対応**: GitHub Actions での自動テスト実行

### ドキュメント最新化 (2025年1月)
- **全READMEファイル更新**: 実装状況に基づく正確な情報反映
- **API エンドポイント完全整理**: 実際のBlueprint実装に基づく20+エンドポイント
- **コンポーネント詳細文書化**: 17 Vue views、11コンポーネント、8 Blueprint詳細
- **マルチエージェント仕様書更新**: Root Coordinator + 4サブエージェント構成
- **開発手順最新化**: セットアップ、ビルド、テスト、デプロイの正確な手順

### 実行コマンド更新
```bash
# テストスイート実行
cd client && npm run test:coverage  # フロントエンド (Jest)
cd server && pytest --cov=app     # バックエンド (pytest)

# ADK エージェント起動 (修正済み設定)
cd agent && adk api_server --host 0.0.0.0 --port 8082 ./agents
```