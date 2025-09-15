# 非同期旅行プラン生成 技術仕様書

## システム要件定義

### 機能要件

#### 非同期プラン生成 (FR1)
- **FR1.1**: ユーザーはプラン生成要求を送信後、即座に他画面に遷移可能
- **FR1.2**: プラン生成処理は最大5分でタイムアウト
- **FR1.3**: 生成完了時にリアルタイム通知を表示
- **FR1.4**: 生成中のプラン数は同時最大10件まで（Pub/Subスケーリング対応）

#### ジョブ管理 (FR2)
- **FR2.1**: ジョブの一意識別ID生成（Firestore document ID使用）
- **FR2.2**: ジョブステータス管理（pending/processing/completed/failed）
- **FR2.3**: ジョブメタデータ管理（作成時間、更新時間、ユーザーID）
- **FR2.4**: ジョブエラー情報とスタックトレース記録

#### 通知システム (FR3) - 更新
- **FR3.1**: Firestore listener によるリアルタイム通知
- **FR3.2**: エラー発生時の詳細エラー通知
- **FR3.3**: 通知の自動消去（3-5秒後）
- **FR3.4**: セッション跨ぎジョブ完了通知

### 非機能要件

#### パフォーマンス (NFR1) - 改善
- **NFR1.1**: ジョブ登録応答時間 < 200ms（Pub/Sub高速化）
- **NFR1.2**: リアルタイム更新（ポーリング不要）
- **NFR1.3**: 同時処理ジョブ数 自動スケーリング
- **NFR1.4**: メモリ使用量 マネージドサービスで最適化

#### 可用性 (NFR2) - 強化
- **NFR2.1**: サービス稼働率 99.95%（Google Cloud SLA）
- **NFR2.2**: ジョブ失敗時の自動リトライ（Pub/Sub Dead Letter対応）
- **NFR2.3**: システム障害時のジョブ永続性（Firestore保証）

#### スケーラビリティ (NFR3) - 向上
- **NFR3.1**: ユーザー数 自動スケーリング対応
- **NFR3.2**: ジョブ処理能力 1000+ ジョブ/分
- **NFR3.3**: Google Cloud インフラによる無制限スケーリング

## システムアーキテクチャ - Pub/Sub設計

### 全体構成図（更新）

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Flask API     │    │   Cloud Pub/Sub │
│   (Vue.js)      │    │   Server        │    │   Topic         │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ Firestore       │◄──►│ PubSubJob       │───►│ travel-jobs     │
│ Real-time       │    │ Processor       │    │                 │
│ Listener        │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         ▲                                               │
         │               ┌─────────────────┐             ▼
         │               │   Firestore     │    ┌─────────────────┐
         └──────────────►│   Jobs          │◄───│  Cloud Function │
                         │   Collection    │    │  Job Processor  │
                         └─────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
                                                ┌─────────────────┐
                                                │   AI Service    │
                                                │ (ADK + Gemini)  │
                                                └─────────────────┘
```
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ ▪ JobPolling    │◀──▶│ ▪ JobManager    │◀──▶│ ▪ TravelPlanner │
│ ▪ Notification  │    │ ▪ ThreadPool    │    │ ▪ Gemini API    │
│ ▪ TaskManagement│    │ ▪ AsyncAPI      │    │ ▪ Maps API      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Database      │
                    │   (Firestore)   │
                    ├─────────────────┤
                    │ ▪ Job Status    │
                    │ ▪ User Data     │
                    │ ▪ Plan Results  │
                    └─────────────────┘
```

### コンポーネント責務

#### JobManager (Backend)
```python
class JobManager:
    responsibilities = [
        "ジョブ登録・管理",
        "ステータス更新",
        "スレッドプール管理",
        "タイムアウト制御"
    ]
    
    interfaces = {
        "create_job": "ジョブ作成",
        "start_job": "ジョブ実行開始", 
        "update_job": "ステータス更新",
        "get_job": "ジョブ情報取得"
    }
```

#### JobPolling (Frontend)
```javascript
class JobPollingService {
    responsibilities = [
        "定期ステータス確認",
        "ポーリング管理",
        "タイムアウト制御",
        "エラーハンドリング"
    ]
    
    interfaces = {
        "startPolling": "ポーリング開始",
        "stopPolling": "ポーリング停止",
        "updateInterval": "間隔調整"
    }
}
```

## データフロー

### 1. プラン生成開始フロー

```
User → PlanWizard → AsyncAPI → JobManager → ThreadPool
 │         │           │          │           │
 │         │           │          │           ▼
 │         │           │          │      AIService
 │         │           │          │           │
 │         │           │          │           ▼
 │         │           │          │      Firestore
 │         │           │          │           │
 │         │           │          ▼           │
 │         │           │      JobCreated      │
 │         │           │          │           │
 │         │           ▼          │           │
 │         │      JobResponse     │           │
 │         │          │           │           │
 │         ▼          │           │           │
 │    HomeRedirect    │           │           │
 │         │          │           │           │
 │         ▼          ▼           ▼           ▼
 └──▶ PollingStart ──────────▶ JobExecution
```

### 2. ステータス更新フロー

```
AIService → JobManager → Firestore
    │           │           │
    │           ▼           │
    │      StatusUpdate     │
    │           │           │
    │           ▼           ▼
    │      DatabaseSync ────┘
    │           │
    ▼           ▼
 Polling ◀─ APIResponse
    │
    ▼
 Notification
```

## API設計

### エンドポイント仕様

#### POST /api/plans/generate-async

**リクエスト**
```json
{
  "keyword": "温泉旅行",
  "options": {
    "plan_count": 3,
    "duration_days": 2,
    "budget_range": "medium"
  }
}
```

**レスポンス（成功）**
```json
{
  "job_id": "job_550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "旅行プラン生成を開始しました",
  "estimated_duration": 120,
  "polling_url": "/api/jobs/job_550e8400-e29b-41d4-a716-446655440000/status"
}
```

**レスポンス（エラー）**
```json
{
  "error": "keyword_required",
  "message": "キーワードが必要です",
  "code": 400
}
```

#### GET /api/jobs/{job_id}/status

**レスポンス（処理中）**
```json
{
  "id": "job_550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": 65,
  "created_at": "2025-09-13T10:30:00Z",
  "updated_at": "2025-09-13T10:31:30Z",
  "estimated_remaining": 45,
  "current_stage": "ai_processing"
}
```

**レスポンス（完了）**
```json
{
  "id": "job_550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": 100,
  "created_at": "2025-09-13T10:30:00Z",
  "updated_at": "2025-09-13T10:32:15Z",
  "completed_at": "2025-09-13T10:32:15Z",
  "result": {
    "plans": [
      {
        "id": 1,
        "title": "草津温泉 癒しの旅",
        "description": "群馬県草津温泉での2日間の癒し旅行",
        "itinerary": [...],
        "places": [...],
        "route_info": {...}
      }
    ],
    "metadata": {
      "generation_time_ms": 135000,
      "model_used": "gemini-2.0-flash",
      "tokens_used": 2450
    }
  }
}
```

### エラーコード定義

| コード | 名前 | 説明 | HTTPステータス |
|--------|------|------|----------------|
| `job_not_found` | ジョブ未発見 | 指定されたジョブIDが存在しない | 404 |
| `job_timeout` | ジョブタイムアウト | 処理時間が制限を超過 | 408 |
| `ai_service_error` | AIサービスエラー | AI処理中にエラーが発生 | 502 |
| `rate_limit_exceeded` | レート制限 | 同時実行ジョブ数上限に到達 | 429 |
| `invalid_parameters` | パラメータ不正 | リクエストパラメータが不正 | 400 |

## UXフロー図

### シナリオ1: 正常完了フロー

```
プラン入力画面
    │
    │ ユーザーがキーワード入力
    │ 「生成開始」ボタンクリック
    ▼
┌─────────────────┐
│ Loading Spinner │ ← API呼び出し（/api/plans/generate-async）
│ "生成開始中..."  │
└─────────────────┘
    │ 0.5秒以内に応答
    ▼
┌─────────────────┐
│ Toast通知       │ ← "旅行プラン生成を開始しました"
│ ホーム画面遷移   │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ ホーム画面      │ ← ポーリング開始（2秒間隔）
│                 │   バックグラウンドで状態監視  
│ [他の機能利用]  │
└─────────────────┘
    │
    │ 1-3分後、完了通知
    ▼
┌─────────────────┐
│ Toast通知       │ ← "旅行プランが完成しました！"
│ "確認する"ボタン │
└─────────────────┘
    │ ユーザーがボタンクリック
    ▼
┌─────────────────┐
│ プラン詳細画面  │ ← 生成されたプランを表示
│ 3つのプラン表示 │
└─────────────────┘
```

### シナリオ2: エラー発生フロー

```
プラン入力画面
    │
    │ ユーザーがキーワード入力
    │ 「生成開始」ボタンクリック
    ▼
┌─────────────────┐
│ Loading Spinner │ ← API呼び出し失敗
│ "生成開始中..."  │
└─────────────────┘
    │ エラー応答
    ▼
┌─────────────────┐
│ Error Toast     │ ← "プラン生成の開始に失敗しました"
│ "再試行"ボタン   │   入力画面に留まる
└─────────────────┘
    │
    │ または、ジョブは開始されたが処理中にエラー
    ▼
┌─────────────────┐
│ ホーム画面      │ ← ポーリング中にエラー検出
│                 │
│ [他の機能利用]  │
└─────────────────┘
    │
    │ エラー通知
    ▼
┌─────────────────┐
│ Error Toast     │ ← "プラン生成に失敗しました"
│ "再試行"ボタン   │
└─────────────────┘
    │ ユーザーがボタンクリック
    ▼
┌─────────────────┐
│ プラン入力画面  │ ← 再入力画面へ遷移
│ 前回の入力復元  │
└─────────────────┘
```

### シナリオ3: タスク管理画面確認

```
ホーム画面
    │
    │ フッターナビゲーション
    │ "タスク"アイコンクリック
    ▼
┌─────────────────┐
│ タスク管理画面  │ ← 進行中のジョブ一覧表示
│                 │
│ ┌─────────────┐ │
│ │プラン生成   │ │ ← 処理中ジョブ
│ │進行中 65%   │ │   プログレスバー表示
│ │─────────    │ │
│ └─────────────┘ │
│                 │
│ ┌─────────────┐ │
│ │プラン生成   │ │ ← 完了ジョブ
│ │完了         │ │   「結果確認」ボタン
│ │[結果確認]   │ │
│ └─────────────┘ │
└─────────────────┘
    │ ユーザーが「結果確認」クリック
    ▼
┌─────────────────┐
│ プラン詳細画面  │ ← 生成結果表示
│ 完成したプラン  │
└─────────────────┘
```

## 実装優先度マトリックス

### HIGH Priority (必須機能)

| 機能 | 理由 | 実装工数 |
|------|------|----------|
| 基本ジョブ管理 | 非同期処理の核心機能 | 3日 |
| ポーリング機能 | 状態確認の基盤 | 2日 |
| 通知システム | UX向上の必須要素 | 1日 |
| エラーハンドリング | 信頼性確保 | 2日 |

### MEDIUM Priority (重要機能)

| 機能 | 理由 | 実装工数 |
|------|------|----------|
| タスク管理画面 | ユーザビリティ向上 | 2日 |
| プログレス表示 | 体感品質向上 | 1日 |
| ジョブ履歴 | トレーサビリティ | 1日 |
| リトライ機能 | 障害耐性 | 1日 |

### LOW Priority (将来機能)

| 機能 | 理由 | 実装工数 |
|------|------|----------|
| リアルタイム更新 | パフォーマンス最適化 | 5日 |
| バッチ処理 | 大規模対応 | 3日 |
| 優先度制御 | 高度な制御 | 2日 |
| プッシュ通知 | モバイル対応 | 4日 |

## テスト戦略

### 単体テスト

#### バックエンド（pytest）
```python
# test_job_manager.py
def test_create_job():
    """ジョブ作成テスト"""
    manager = JobManager()
    job_id = manager.create_job(
        user_id="test_user",
        job_type="plan_generation", 
        params={"keyword": "test"}
    )
    
    job = manager.get_job(job_id)
    assert job is not None
    assert job['status'] == 'pending'
    assert job['user_id'] == 'test_user'

def test_job_execution():
    """ジョブ実行テスト"""
    def mock_job_function(job_id, manager):
        return {"result": "test_data"}
    
    manager = JobManager()
    job_id = manager.create_job("user", "test", {})
    manager.start_job(job_id, mock_job_function)
    
    # 完了まで待機
    time.sleep(1)
    
    job = manager.get_job(job_id)
    assert job['status'] == 'completed'
    assert job['result'] == {"result": "test_data"}
```

#### フロントエンド（Jest）
```javascript
// jobPolling.test.js
import { jobPolling } from '@/services/jobPolling'

describe('JobPollingService', () => {
  beforeEach(() => {
    fetch.resetMocks()
  })

  test('should start polling and handle completion', async () => {
    const mockCallback = jest.fn()
    
    // Mock API responses
    fetch
      .mockResponseOnce(JSON.stringify({ status: 'processing', progress: 50 }))
      .mockResponseOnce(JSON.stringify({ status: 'completed', result: {} }))
    
    await jobPolling.startPolling('test-job-id', mockCallback, { interval: 100 })
    
    await new Promise(resolve => setTimeout(resolve, 300))
    
    expect(mockCallback).toHaveBeenCalledWith(expect.objectContaining({
      status: 'completed'
    }))
  })

  test('should handle polling errors', async () => {
    const mockCallback = jest.fn()
    
    fetch.mockReject(new Error('Network error'))
    
    await jobPolling.startPolling('test-job-id', mockCallback)
    
    expect(mockCallback).toHaveBeenCalledWith(expect.objectContaining({
      status: 'error'
    }))
  })
})
```

#### モバイルUI（Responsive Design）
```javascript
// mobileUI.test.js - レスポンシブデザインテスト
describe('Mobile UI Optimization', () => {
  test('PlansListView should prevent card clipping on mobile', async () => {
    // モバイルビューポート設定
    Object.defineProperty(window, 'innerWidth', { value: 375 })
    Object.defineProperty(window, 'innerHeight', { value: 667 })
    
    const wrapper = mount(PlansListView)
    
    // カードコンテナの横スクロール防止を確認
    const cards = wrapper.find('.cards')
    expect(cards.classes()).toContain('overflow-x-hidden')
    
    // グリッドレイアウトが1列になることを確認
    expect(getComputedStyle(cards.element).gridTemplateColumns).toBe('1fr')
  })

  test('Touch targets should meet WCAG AA standards', () => {
    const wrapper = mount(PlansListView)
    const toggleButton = wrapper.find('.toggle-btn')
    
    // 最小44px タッチターゲットサイズを確認
    const computedStyle = getComputedStyle(toggleButton.element)
    expect(parseInt(computedStyle.minWidth)).toBeGreaterThanOrEqual(44)
    expect(parseInt(computedStyle.minHeight)).toBeGreaterThanOrEqual(44)
  })

  test('Dynamic viewport height should be supported', () => {
    const wrapper = mount(App)
    const container = wrapper.find('#app-container')
    
    // 動的ビューポート高さの使用を確認
    expect(getComputedStyle(container.element).height).toContain('100dvh')
  })

  test('Safe area insets should be properly handled', () => {
    // Safe area inset環境変数を模擬
    document.documentElement.style.setProperty('--safe-area-inset-left', '20px')
    
    const wrapper = mount(App)
    const header = wrapper.find('.site-header')
    
    // セーフエリア対応パディングを確認
    expect(getComputedStyle(header.element).paddingLeft).toContain('calc')
  })
})
```

### 統合テスト

#### エンドツーエンドフロー
```javascript
// e2e/async-plan-generation.test.js
describe('Async Plan Generation', () => {
  test('complete user journey', async () => {
    // 1. プラン生成開始
    await page.goto('/travel-wizard')
    await page.fill('[data-testid="keyword-input"]', '温泉旅行')
    await page.click('[data-testid="generate-button"]')
    
    // 2. 通知確認
    await expect(page.locator('[data-testid="toast"]')).toHaveText(/生成を開始しました/)
    
    // 3. ホーム画面遷移確認
    await expect(page).toHaveURL('/')
    
    // 4. タスク画面確認
    await page.click('[data-testid="tasks-tab"]')
    await expect(page.locator('[data-testid="job-card"]')).toBeVisible()
    
    // 5. 完了通知確認（Mock APIで即座に完了）
    await expect(page.locator('[data-testid="success-toast"]')).toBeVisible()
  })
})
```

### パフォーマンステスト

#### 負荷テスト
```python
# locust_test.py
from locust import HttpUser, task, between

class PlanGenerationUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        # ログイン処理
        self.client.post("/api/auth/login", json={
            "username": "test_user",
            "password": "test_pass"
        })
    
    @task(3)
    def generate_plan_async(self):
        """非同期プラン生成負荷テスト"""
        response = self.client.post("/api/plans/generate-async", json={
            "keyword": "温泉旅行"
        })
        
        if response.status_code == 200:
            job_id = response.json()['job_id']
            
            # ポーリング
            for _ in range(30):  # 最大60秒
                status_resp = self.client.get(f"/api/jobs/{job_id}/status")
                if status_resp.json()['status'] in ['completed', 'failed']:
                    break
                time.sleep(2)
    
    @task(1)
    def check_tasks(self):
        """タスク一覧確認"""
        self.client.get("/api/jobs/user/current")
```

## 監視・運用

### メトリクス収集

#### ジョブメトリクス
```python
# metrics.py
class JobMetrics:
    def __init__(self):
        self.job_counter = Counter('jobs_total', 'Total jobs', ['type', 'status'])
        self.job_duration = Histogram('job_duration_seconds', 'Job duration')
        self.active_jobs = Gauge('active_jobs', 'Currently active jobs')
    
    def record_job_start(self, job_type):
        self.job_counter.labels(type=job_type, status='started').inc()
        self.active_jobs.inc()
    
    def record_job_completion(self, job_type, duration, status):
        self.job_counter.labels(type=job_type, status=status).inc()
        self.job_duration.observe(duration)
        self.active_jobs.dec()
```

#### アラート設定
```yaml
# alerts.yml
groups:
- name: async_jobs
  rules:
  - alert: HighJobFailureRate
    expr: rate(jobs_total{status="failed"}[5m]) > 0.1
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "Job failure rate is high"
      
  - alert: JobQueueBacklog
    expr: active_jobs > 10
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Job queue has significant backlog"
```

### ログ設計

#### 構造化ログ
```python
# logging_config.py
import structlog

logger = structlog.get_logger()

# ジョブ開始ログ
logger.info("job_started", 
    job_id=job_id,
    user_id=user_id,
    job_type=job_type,
    params=params
)

# ジョブ完了ログ  
logger.info("job_completed",
    job_id=job_id,
    duration_ms=duration,
    status=status,
    result_size=len(result)
)

# エラーログ
logger.error("job_failed",
    job_id=job_id,
    error_type=type(error).__name__,
    error_message=str(error),
    traceback=traceback.format_exc()
)
```

## セキュリティ考慮事項

### 認証・認可
- **ジョブ所有者チェック**: ユーザーは自分のジョブのみアクセス可能
- **レート制限**: ユーザー毎の同時ジョブ数制限
- **APIキー保護**: AI APIキーの安全な管理

### データ保護
- **ジョブデータ暗号化**: 機密情報の暗号化保存
- **ログマスキング**: 個人情報のログマスク
- **データ保持期間**: ジョブデータの自動削除（30日後）

### 入力検証
- **パラメータサニタイズ**: XSS/SQLインジェクション対策
- **ファイルサイズ制限**: 大量データ攻撃防止
- **入力長制限**: DoS攻撃防止

## まとめ

本技術仕様書により、非同期旅行プラン生成システムの包括的な実装ガイドラインを提供しました。段階的な実装アプローチにより、リスクを最小化しながら、ユーザー体験の大幅な改善を実現できます。

フェーズ1の基本実装（約8日間）で、Issue #199の主要要求は満たすことができ、その後の拡張により更なる価値を提供できます。

---

**最終更新**: 2025年9月15日