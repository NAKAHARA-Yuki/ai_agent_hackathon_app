# AIエージェント実装仕様書

## 概要

いざ旅(Izatabi)アプリケーションは、**Google Agent Development Kit (ADK)** を基盤とした階層型マルチエージェントシステムを実装しています。このドキュメントでは、エージェントの詳細な実装仕様、統合パターン、運用方法について解説します。

## エージェントアーキテクチャ

### システム構成図

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Vue.js)                        │
│                   http://localhost:5173                     │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTP API calls
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                  Backend (Flask)                            │
│                 http://localhost:8080                       │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │            /api/agent/chat endpoint                     │ │
│  │              (blueprints/ai.py)                         │ │
│  └─────────────────────┬───────────────────────────────────┘ │
└────────────────────────┼─────────────────────────────────────┘
                         │ ADK API calls
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              ADK Agent Service                              │
│                http://localhost:8082                        │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │          Root Coordinator Agent                         │ │
│  │         (Gemini 2.5 Flash Lite)                        │ │
│  │  ┌─────────────────┐  ┌─────────────────────────────────┐ │ │
│  │  │ Travel Planner  │  │    Travel Advisor             │ │ │
│  │  │ Agent           │  │    Agent                      │ │ │
│  │  │ (Gemini 2.5 Pro)│  │ (Gemini 2.5 Pro)             │ │ │
│  │  └─────────────────┘  └─────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────┬───────────────────────────────┬─────────────┘
                  │                               │
                  ▼                               ▼
┌─────────────────────────────┐    ┌─────────────────────────────┐
│      Google Maps MCP        │    │      Gemini API             │
│   (MCP Server)             │    │    (AI Generation)          │
│  http://localhost:3000      │    │                             │
└─────────────────────────────┘    └─────────────────────────────┘
```

### エージェント階層構造

#### 1. Root Coordinator Agent
**ファイル**: `agent/agents/root_coordinator/agent.py`

**責任範囲**:
- ユーザーリクエストの解析・分類
- 適切なサブエージェントへのルーティング
- サブエージェント応答の透過的な転送

**ルーティング判断基準**:
```python
判断基準：
- 新しい旅行プランの作成依頼 → travel_planner
- 既存プランの修正、当日のトラブル対応、リアルタイム情報 → travel_advisor
- 判断が困難な場合は travel_planner を選択
```

**設定詳細**:
```python
root_agent = LlmAgent(
    name="root_coordinator",
    model="gemini-2.5-flash-lite",  # 高速レスポンス重視
    description="Coordinate requests to appropriate sub-agents",
    instruction=ROOT_COORDINATOR_INSTRUCTION,
    sub_agents=[travel_planner_agent, travel_advisor_agent],
    tools=[],  # ルートエージェントは直接ツールを使用しない
)
```

#### 2. Travel Planner Agent
**ファイル**: `agent/agents/root_coordinator/travel_planner/agent.py`

**責任範囲**:
- 新規旅行プランの生成（3案必須）
- ペルソナ/プロファイル情報の活用
- 構造化JSON形式での出力
- 地理的合理性・季節感・移動時間の考慮

**出力スキーマ**:
```json
{
  "summary": "string",
  "plans": [
    {
      "title": "string (25文字以内)",
      "tags": ["string (1-6語)"],
      "brief": "string (40字以内)",
      "itinerary": [
        {
          "day": 1,
          "items": [
            {
              "time": "HH:MM",
              "title": "string",
              "detail": "string|null",
              "transport": {
                "mode": "driving|walking|bicycling|transit",
                "estimated_duration": "string|null",
                "distance_km": "number|null"
              }
            }
          ]
        }
      ],
      "places": [
        {
          "name": "string",
          "lat": "number|null",
          "lng": "number|null",
          "note": "string|null"
        }
      ],
      "route_info": {
        "origin": "string",
        "destination": "string", 
        "waypoints": ["string"],
        "mode": "driving|walking|bicycling|transit",
        "estimated_duration": "string|null"
      },
      "text": "string"
    }
  ]
}
```

**制約・品質保証**:
- plans は必ず3件
- title 25文字以内、tags 各1-6語、brief 40字以内
- itinerary は day 昇順、time=HH:MM形式、1日2-8 items
- places 最大10件（重複名除外）
- JSONコードフェンス・Markdown記法禁止
- 危険・非現実・閉鎖施設の除外

#### 3. Travel Advisor Agent  
**ファイル**: `agent/agents/root_coordinator/travel_advisor/agent.py`

**責任範囲**:
- 既存プランベースの当日サポート
- リアルタイム状況への対応・代案提示
- 緊急時・トラブル時のアドバイス

**対応シナリオ**:
- 天候変化 → 屋内代替案提案
- 交通遅延 → 時間調整アドバイス
- 現在地情報 → 最適ルート案内
- 営業時間確認 → 混雑状況・代案情報
- 緊急事態 → サポート情報提供

**出力スキーマ**:
```json
{
  "response_type": "advice|alternative|information|emergency",
  "message": "string (200文字以内)",
  "suggestions": [
    {
      "type": "location|timing|activity|route",
      "title": "string",
      "description": "string", 
      "priority": "high|medium|low",
      "estimated_time": "string|null",
      "location": {
        "name": "string",
        "lat": "number|null",
        "lng": "number|null"
      }
    }
  ],
  "updated_schedule": [
    {
      "time": "HH:MM",
      "activity": "string",
      "location": "string", 
      "notes": "string|null"
    }
  ],
  "route_info": { /* 同Travel Planner */ }
}
```

## MCP (Model Context Protocol) 統合

### Google Maps MCP (Model Context Protocol)

**統合方式**:
```python
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

tools=[MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command='npx',
            args=["-y", "@modelcontextprotocol/server-google-maps"],
            env={"GOOGLE_MAPS_API_KEY": google_maps_api_key}
        ),
        timeout=10,
    ),
)]
```

**利用可能ツール**:
- `geocode` - 地名→緯度経度変換
- `reverse_geocode` - 緯度経度→地名変換  
- `search_places` - 場所検索
- `place_details` - 場所詳細情報取得
- `distance_matrix` - 距離・所要時間計算
- `directions` - 経路案内
- `elevation` - 標高取得

## ADK統合パターン

### セッション管理

**ADK API Server プロトコル**:
1. **セッション作成** (冪等):
   ```
   POST /apps/{app_name}/users/{user_id}/sessions/{session_id}
   Body: {}
   ```
   
2. **エージェント実行**:
   ```
   POST /run
   Body: {
     "app_name": "string",
     "user_id": "string", 
     "session_id": "string",
     "new_message": {
       "role": "user",
       "parts": [{"text": "ユーザーメッセージ"}]
     }
   }
   ```

3. **応答処理**: 
   - events配列を受信
   - modelロールのメッセージを最終応答として抽出

### Flask統合実装

**エンドポイント**: `POST /api/agent/chat` (server/blueprints/ai.py)

**処理フロー**:
```python
def agent_chat():
    # 1. 認証確認
    claims = claims_or_dev()
    
    # 2. エージェント可用性チェック  
    if not agent_configured:
        # Gemini APIフォールバック
        return gemini_direct_call()
    
    # 3. ADK Agent呼び出し
    events = call_adk_agent_chat(
        app_name="travel_assistant",
        user_id=claims['sub'],
        session_id=session_id,
        message_text=message,
        timeout_sec=AGENT_HTTP_TIMEOUT
    )
    
    # 4. 応答抽出・正規化
    for event in events:
        if event.get('role') == 'model':
            reply = extract_model_reply(event)
            places, route_info = extract_structured_data(reply)
            
    # 5. レスポンス構築
    return jsonify({
        'reply': reply,
        'places': places,
        'route_info': route_info,
        'citations': grounding_info,
        'grounding_html': grounding_html
    })
```

### エラーハンドリング・フォールバック

**503エラー指数バックオフ**:
```python
def retry_on_503(func, max_retries=3, base_delay=1.0):
    for attempt in range(max_retries + 1):
        try:
            return func()
        except requests.RequestException as e:
            if e.response.status_code == 503:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                time.sleep(delay)
            else:
                raise
```

**Geminiフォールバック**:
- エージェントサービス不可時の自動切り替え
- 基本的な旅行提案機能を維持
- 構造化出力は制限される

## デプロイメント・運用

### 環境変数設定

```bash
# === エージェント基本設定 ===
AGENT_BASE_URL=http://agent-service:8080     # ADK API Server URL
AGENT_API_KEY=                               # Bearer認証トークン（任意）
AGENT_HTTP_TIMEOUT=180                       # HTTPタイムアウト（秒）

# === AIモデル設定 ===
GEMINI_API_KEY=your_gemini_api_key          # Gemini API認証キー  
GEMINI_MODEL=gemini-2.5-pro                 # エージェント用モデル

# === MCP設定 ===
GOOGLE_MAPS_API_KEY=your_maps_api_key       # Maps MCP用APIキー
MAPS_MCP_ENDPOINT_URL=http://mcp:3000/tools/retrieve-google-maps-platform-docs

# === ログ・デバッグ設定 ===
LOG_LEVEL=INFO                              # ログレベル
CLOUD_LOG_FULL_PAYLOAD=1                    # 詳細ペイロードログ（開発用）
AGENT_LOG_RAW=full                          # エージェント生レスポンスログ（開発用）
```

### Docker Compose設定

```yaml
# docker-compose.dev.yml
version: '3.8'
services:
  # メインアプリケーション
  app:
    build: .
    ports:
      - "8080:8080"
    environment:
      - AGENT_BASE_URL=http://agent-service:8080
      - GEMINI_API_KEY=${GEMINI_API_KEY}
    depends_on:
      - agent-service
      
  # ADKエージェントサービス  
  agent-service:
    build: ./agent
    ports:
      - "8082:8080"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - GOOGLE_MAPS_API_KEY=${GOOGLE_MAPS_API_KEY}
      - MAPS_MCP_ENDPOINT_URL=http://mcp-service:3000/tools/retrieve-google-maps-platform-docs
    depends_on:
      - mcp-service

  # Google Maps MCPサーバー
  mcp-service:
    build: ./mcp  
    ports:
      - "3000:3000"
    command: npx @googlemaps/code-assist-mcp --port 3000
```

### Cloud Run デプロイメント

**個別サービス構成**:
- `travel-quiz-app` - メインアプリケーション
- `travel-agent-service` - ADKエージェントサービス  
- `maps-mcp-service` - Google Maps MCPサーバー

**GitHub Actions CI/CD**:
```yaml
# .github/workflows/deploy-cloud-run.yml
name: Deploy to Cloud Run
on:
  push:
    branches: [main, dev]
jobs:
  deploy-agent:
    runs-on: ubuntu-latest
    steps:
      - name: Build Agent Service
        run: docker build -t gcr.io/$PROJECT_ID/agent-service ./agent
      - name: Deploy Agent Service  
        run: gcloud run deploy travel-agent-service --image gcr.io/$PROJECT_ID/agent-service
```

## パフォーマンス・監視

### メトリクス収集

**JSON応答品質**:
```python
# アプリケーションレベルカウンター
app.AGENT_JSON_OK = 0      # 正常JSON応答数
app.AGENT_JSON_FAIL = 0    # JSON解析失敗数
```

**レスポンス時間追跡**:
```python
# リクエスト開始時刻記録
@app.before_request
def _start_timer():
    request._start_time = monotonic()
    request._trace_id = f"{random.getrandbits(64):016x}"

# レスポンス時間ログ    
@app.after_request  
def _log_request(resp):
    dur_ms = (monotonic() - request._start_time) * 1000
    logger.info(f"HTTP {request.method} {request.path} -> {resp.status_code} {int(dur_ms)}ms trace={request._trace_id}")
```

### エラー監視・アラート

**主要エラーパターン**:
- ADK Agent接続エラー (503, timeout, connection errors)
- JSON構造解析エラー (plans配列不正、必須フィールド欠損)  
- MCP Tool呼び出しエラー (Maps API制限、認証エラー)
- Gemini API制限エラー (quota exceeded, rate limiting)

**推奨監視項目**:
- エージェント応答時間 (P95 < 30秒目標)
- JSON応答成功率 (> 95%目標) 
- エージェントサービス可用性 (> 99%目標)
- MCP Tool成功率 (> 90%目標)

## 開発・デバッグガイド

### ローカル開発環境

**個別起動**:
```bash
# 1. MCP サーバー起動
cd mcp
npx @googlemaps/code-assist-mcp --port 3000

# 2. ADK エージェント起動  
cd agent
pip install -r requirements.txt
adk api_server --host 0.0.0.0 --port 8082 ./agents

# 3. Flask バックエンド起動
cd server  
AGENT_BASE_URL=http://localhost:8082 python app.py

# 4. Vue.js フロントエンド起動
cd client
npm run dev
```

**Docker Compose起動**:
```bash
# 全サービス一括起動
docker-compose -f docker-compose.dev.yml up -d

# ログ確認
docker-compose -f docker-compose.dev.yml logs -f agent-service
```

### デバッグ設定

**詳細ログ有効化**:
```bash
export LOG_LEVEL=DEBUG
export CLOUD_LOG_FULL_PAYLOAD=1  
export AGENT_LOG_RAW=full
```

**ADK Dev UI アクセス**:
- URL: http://localhost:8082
- エージェントとの直接対話テスト
- MCP Tool動作確認
- セッション状態確認

### トラブルシューティング

**よくある問題と対処法**:

1. **Agent接続エラー**:
   ```
   エラー: Agent service not configured
   対処: AGENT_BASE_URL環境変数を確認、ADKサービス起動状態確認
   ```

2. **JSON解析エラー**:
   ```
   エラー: AGENT_JSON_FAIL カウンター増加
   対処: エージェント instruction の JSON スキーマ指示を確認
   ```

3. **MCP Tool エラー**:
   ```  
   エラー: Maps API呼び出し失敗
   対処: GOOGLE_MAPS_API_KEY確認、API使用量制限確認
   ```

4. **メモリ・CPU使用量**:
   ```
   対処: ADKエージェントのmodel設定を軽量版に変更
   gemini-2.5-pro → gemini-2.5-flash-lite
   ```

## まとめ

本実装では、Google ADKを活用した階層型マルチエージェントシステムにより、高品質で構造化された旅行計画サービスを実現しています。各エージェントの役割分担、MCP統合によるリアルタイム情報活用、包括的なエラーハンドリング・フォールバック機構により、信頼性の高いAIサービスを提供します。

開発・運用時は本ドキュメントを参照し、適切な監視・デバッグ手法を活用してください。