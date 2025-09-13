# 非同期旅行プラン生成 実装方法検討書

## 概要

本ドキュメントは、Issue #199「旅行プランの作成を非同期にしたい」に対する実装方法の詳細検討結果です。現在の同期処理によるUX問題を解決し、将来の画像生成機能追加に備えた設計を提案します。

## 現状の問題分析

### 現在の実装状況
- **フロントエンド**: Vue.js、同期的なHTTPリクエスト
- **バックエンド**: Flask、ADKエージェント統合
- **AI処理**: Gemini API、ADK Agent Service
- **データベース**: Firestore

### 主要なプラン生成エンドポイント
1. `/api/generate_plan` - レガシー直接Gemini呼び出し（quizStore.js使用）
2. `/api/agent/generate_plan` - ADKエージェント経由（TravelPlanWizardView.vue使用）

### 現在の問題点
- ✗ プラン生成に数十秒〜数分の時間が必要
- ✗ 同期処理により、ユーザーは待機画面から移動できない
- ✗ 将来の画像生成機能追加でさらに処理時間が延長
- ✗ ネットワーク切断やタイムアウトでプラン消失
- ✗ 複数プラン同時生成不可

## 実装アプローチの比較検討

### アプローチ1: シンプルジョブキュー + ポーリング
**実装内容:**
```python
# Backend: Job Management System
class JobManager:
    def __init__(self):
        self.jobs = {}  # job_id -> job_data
    
    def create_job(self, user_id, job_type, params):
        job_id = str(uuid.uuid4())
        job = {
            'id': job_id,
            'user_id': user_id,
            'type': job_type,
            'status': 'pending',
            'params': params,
            'created_at': datetime.now(),
            'result': None,
            'error': None
        }
        self.jobs[job_id] = job
        return job_id
```

**メリット:**
- ✅ 実装が簡単
- ✅ 既存インフラ不要（インメモリキュー）
- ✅ 後方互換性維持

**デメリット:**
- ❌ ポーリングによる余計なAPI呼び出し
- ❌ リアルタイム性が低い
- ❌ サーバー再起動でジョブ消失

### アプローチ2: WebSocket リアルタイム更新
**実装内容:**
```python
# Flask-SocketIO使用
from flask_socketio import SocketIO, emit

@socketio.on('start_plan_generation')
def handle_plan_generation(data):
    job_id = create_background_job(data)
    emit('job_started', {'job_id': job_id})
```

**メリット:**
- ✅ リアルタイム更新
- ✅ 効率的な通信
- ✅ 優れたUX

**デメリット:**
- ❌ 実装複雑度高
- ❌ WebSocketインフラ必要
- ❌ 接続断対応が必要

### アプローチ3: Server-Sent Events (SSE)
**実装内容:**
```python
@app.route('/api/jobs/<job_id>/stream')
def job_stream(job_id):
    def generate():
        while True:
            status = get_job_status(job_id)
            yield f"data: {json.dumps(status)}\n\n"
            if status['status'] in ['completed', 'failed']:
                break
            time.sleep(2)
    return Response(generate(), mimetype='text/plain')
```

**メリット:**
- ✅ WebSocketより簡単
- ✅ リアルタイム更新
- ✅ 自動再接続

**デメリット:**
- ❌ 単方向通信のみ
- ❌ ブラウザサポート限定

### アプローチ4: Firestore リアルタイムリスナー
**実装内容:**
```javascript
// Frontend: Firestore listener
import { onSnapshot } from 'firebase/firestore'

const unsubscribe = onSnapshot(
  doc(db, 'jobs', jobId),
  (doc) => {
    const status = doc.data()
    if (status.status === 'completed') {
      showNotification('プラン生成完了！')
    }
  }
)
```

**メリット:**
- ✅ 既存Firestoreインフラ活用
- ✅ リアルタイム更新
- ✅ 永続的ジョブステータス
- ✅ セッション跨ぎ対応

**デメリット:**
- ❌ Firestoreへの依存増加
- ❌ 追加読み込みコスト

## 推奨実装方針

### フェーズ1: ジョブキュー + ポーリング
初期実装として最もリスクが低く、効果が高いアプローチ1を推奨します。

#### バックエンド実装

**1. ジョブ管理システム**
```python
# server/utils/job_manager.py
import uuid
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional

class JobManager:
    def __init__(self, max_workers=3):
        self.jobs: Dict[str, Dict] = {}
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.lock = threading.Lock()
    
    def create_job(self, user_id: str, job_type: str, params: Dict) -> str:
        job_id = str(uuid.uuid4())
        with self.lock:
            self.jobs[job_id] = {
                'id': job_id,
                'user_id': user_id,
                'type': job_type,
                'status': 'pending',
                'params': params,
                'created_at': datetime.now(),
                'updated_at': datetime.now(),
                'result': None,
                'error': None,
                'progress': 0
            }
        return job_id
    
    def start_job(self, job_id: str, job_function):
        def run_job():
            self.update_job(job_id, status='processing')
            try:
                result = job_function(job_id, self)
                self.update_job(job_id, status='completed', result=result)
            except Exception as e:
                self.update_job(job_id, status='failed', error=str(e))
        
        self.executor.submit(run_job)
    
    def update_job(self, job_id: str, **updates):
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id].update(updates)
                self.jobs[job_id]['updated_at'] = datetime.now()
    
    def get_job(self, job_id: str) -> Optional[Dict]:
        with self.lock:
            return self.jobs.get(job_id)
    
    def get_user_jobs(self, user_id: str) -> List[Dict]:
        with self.lock:
            return [job for job in self.jobs.values() if job['user_id'] == user_id]

# Global job manager instance
job_manager = JobManager()
```

**2. 新しいAPIエンドポイント**
```python
# server/blueprints/async_plans.py
from flask import Blueprint, request, jsonify
from utils.job_manager import job_manager
from utils.auth import claims_or_dev
from utils.ai_processing import call_adk_agent_chat

async_plans_bp = Blueprint('async_plans', __name__)

@async_plans_bp.post('/api/plans/generate-async')
def generate_plan_async():
    """非同期旅行プラン生成開始"""
    claims = claims_or_dev()
    if not claims:
        return jsonify({'error': 'auth_required'}), 401
    
    user_id = claims['sub']
    data = request.get_json() or {}
    keyword = data.get('keyword', '').strip()
    
    if not keyword:
        return jsonify({'error': 'keyword_required'}), 400
    
    # ジョブ作成
    job_id = job_manager.create_job(
        user_id=user_id,
        job_type='plan_generation',
        params={'keyword': keyword}
    )
    
    # バックグラウンド処理開始
    job_manager.start_job(job_id, process_plan_generation)
    
    return jsonify({
        'job_id': job_id,
        'status': 'pending',
        'message': '旅行プラン生成を開始しました'
    })

@async_plans_bp.get('/api/jobs/<job_id>/status')
def get_job_status(job_id):
    """ジョブステータス取得"""
    job = job_manager.get_job(job_id)
    if not job:
        return jsonify({'error': 'job_not_found'}), 404
    
    # 時刻をJSON serializable形式に変換
    job_data = job.copy()
    job_data['created_at'] = job_data['created_at'].isoformat()
    job_data['updated_at'] = job_data['updated_at'].isoformat()
    
    return jsonify(job_data)

@async_plans_bp.get('/api/jobs/user/<user_id>')
def get_user_jobs(user_id):
    """ユーザーのジョブ一覧取得"""
    jobs = job_manager.get_user_jobs(user_id)
    
    # JSON serializable形式に変換
    jobs_data = []
    for job in jobs:
        job_data = job.copy()
        job_data['created_at'] = job_data['created_at'].isoformat()
        job_data['updated_at'] = job_data['updated_at'].isoformat()
        jobs_data.append(job_data)
    
    return jsonify({'jobs': jobs_data})

def process_plan_generation(job_id: str, job_manager):
    """プラン生成処理（バックグラウンド実行）"""
    job = job_manager.get_job(job_id)
    if not job:
        raise Exception("Job not found")
    
    user_id = job['user_id']
    keyword = job['params']['keyword']
    
    try:
        # 進捗更新
        job_manager.update_job(job_id, progress=25)
        
        # ADKエージェント呼び出し
        events = call_adk_agent_chat(
            'root_coordinator',
            user_id,
            'default',
            f"以下のキーワードで3つの旅行プランを提案してください: {keyword}",
            timeout_sec=120
        )
        
        job_manager.update_job(job_id, progress=75)
        
        # レスポンス処理（既存のコードを再利用）
        # ... プラン抽出・正規化処理 ...
        
        result = {
            'plans': processed_plans,
            'keyword': keyword,
            'generated_at': datetime.now().isoformat()
        }
        
        return result
        
    except Exception as e:
        logger.exception(f"Plan generation failed for job {job_id}")
        raise
```

#### フロントエンド実装

**1. ジョブポーリングサービス**
```javascript
// client/src/services/jobPolling.js
class JobPollingService {
    constructor() {
        this.activePolls = new Map()
        this.defaultInterval = 2000 // 2秒間隔
    }
    
    async startPolling(jobId, callback, options = {}) {
        const interval = options.interval || this.defaultInterval
        const maxDuration = options.maxDuration || 300000 // 5分
        const startTime = Date.now()
        
        const poll = async () => {
            try {
                const response = await fetch(`/api/jobs/${jobId}/status`, {
                    headers: this.getAuthHeaders()
                })
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`)
                }
                
                const job = await response.json()
                callback(job)
                
                // 完了状態または最大時間経過で終了
                if (job.status === 'completed' || job.status === 'failed') {
                    this.stopPolling(jobId)
                    return
                }
                
                if (Date.now() - startTime > maxDuration) {
                    this.stopPolling(jobId)
                    callback({ status: 'timeout', error: 'Polling timeout' })
                    return
                }
                
                // 次のポーリングをスケジュール
                const timeoutId = setTimeout(poll, interval)
                this.activePolls.set(jobId, timeoutId)
                
            } catch (error) {
                console.error('Polling error:', error)
                callback({ status: 'error', error: error.message })
                this.stopPolling(jobId)
            }
        }
        
        // 最初のポーリング実行
        poll()
    }
    
    stopPolling(jobId) {
        const timeoutId = this.activePolls.get(jobId)
        if (timeoutId) {
            clearTimeout(timeoutId)
            this.activePolls.delete(jobId)
        }
    }
    
    stopAllPolling() {
        for (const [jobId] of this.activePolls) {
            this.stopPolling(jobId)
        }
    }
    
    getAuthHeaders() {
        const token = localStorage.getItem('authToken')
        return token ? { 'Authorization': `Bearer ${token}` } : {}
    }
}

export const jobPolling = new JobPollingService()
```

**2. 通知管理ストア**
```javascript
// client/src/stores/notificationStore.js
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useNotificationStore = defineStore('notification', () => {
    const notifications = ref([])
    
    function addNotification(message, type = 'info', duration = 3000) {
        const id = Date.now() + Math.random()
        const notification = {
            id,
            message,
            type,
            duration,
            timestamp: new Date()
        }
        
        notifications.value.push(notification)
        
        // 自動削除
        setTimeout(() => {
            removeNotification(id)
        }, duration)
        
        return id
    }
    
    function removeNotification(id) {
        const index = notifications.value.findIndex(n => n.id === id)
        if (index > -1) {
            notifications.value.splice(index, 1)
        }
    }
    
    function showSuccess(message) {
        return addNotification(message, 'success', 4000)
    }
    
    function showError(message) {
        return addNotification(message, 'error', 5000)
    }
    
    function showInfo(message) {
        return addNotification(message, 'info', 3000)
    }
    
    return {
        notifications,
        addNotification,
        removeNotification,
        showSuccess,
        showError,
        showInfo
    }
})
```

**3. 非同期プラン生成フロー**
```javascript
// client/src/views/TravelPlanWizardView.vue の更新
import { jobPolling } from '@/services/jobPolling'
import { useNotificationStore } from '@/stores/notificationStore'

const notifications = useNotificationStore()

async function handleCreatePlanAsync(keyword) {
    if (!keyword || currentView.value !== 'input') return
    
    try {
        // 1. 非同期ジョブ開始
        const response = await fetch('/api/plans/generate-async', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                ...auth.authHeader()
            },
            body: JSON.stringify({ keyword })
        })
        
        if (!response.ok) throw new Error('Failed to start plan generation')
        
        const { job_id } = await response.json()
        
        // 2. 処理開始通知
        notifications.showInfo('旅行プラン生成を開始しました。ホーム画面でお待ちください。')
        
        // 3. ホーム画面に戻る
        router.push('/')
        
        // 4. ポーリング開始
        jobPolling.startPolling(job_id, (job) => {
            if (job.status === 'completed') {
                notifications.showSuccess('旅行プランが完成しました！確認してください。')
                // プラン詳細ページへの誘導
                router.push(`/plans/${job_id}`)
            } else if (job.status === 'failed') {
                notifications.showError('プラン生成に失敗しました。再度お試しください。')
            } else if (job.status === 'processing') {
                // プログレス表示可能
                const progress = job.progress || 0
                notifications.showInfo(`生成中... (${progress}%)`)
            }
        })
        
    } catch (error) {
        console.error('Plan generation error:', error)
        notifications.showError('プラン生成の開始に失敗しました。')
    }
}
```

**4. タスク管理画面の更新**
```vue
<!-- client/src/views/TasksView.vue -->
<template>
  <div class="tasks-view">
    <h1>進行中のタスク</h1>
    
    <div v-if="loading" class="loading">
      タスクを読み込み中...
    </div>
    
    <div v-else-if="jobs.length === 0" class="empty-state">
      <p>進行中のタスクはありません</p>
    </div>
    
    <div v-else class="jobs-list">
      <div v-for="job in jobs" :key="job.id" class="job-card">
        <div class="job-header">
          <h3>{{ getJobTitle(job.type) }}</h3>
          <span class="status" :class="job.status">{{ getStatusText(job.status) }}</span>
        </div>
        
        <div class="job-details">
          <p class="keyword">キーワード: {{ job.params.keyword }}</p>
          <p class="timestamp">開始: {{ formatTime(job.created_at) }}</p>
        </div>
        
        <div v-if="job.status === 'processing'" class="progress">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: `${job.progress || 0}%` }"></div>
          </div>
          <span class="progress-text">{{ job.progress || 0 }}%</span>
        </div>
        
        <div v-if="job.status === 'completed'" class="actions">
          <button @click="viewResult(job)" class="btn-primary">結果を確認</button>
        </div>
        
        <div v-if="job.status === 'failed'" class="error">
          <p class="error-message">{{ job.error }}</p>
          <button @click="retryJob(job)" class="btn-secondary">再試行</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/authStore'

const auth = useAuthStore()
const jobs = ref([])
const loading = ref(false)

async function loadUserJobs() {
    if (!auth.user?.id) return
    
    loading.value = true
    try {
        const response = await fetch(`/api/jobs/user/${auth.user.id}`, {
            headers: auth.authHeader()
        })
        
        if (response.ok) {
            const data = await response.json()
            jobs.value = data.jobs || []
        }
    } catch (error) {
        console.error('Failed to load jobs:', error)
    } finally {
        loading.value = false
    }
}

function getJobTitle(type) {
    const titles = {
        'plan_generation': '旅行プラン生成',
        'image_generation': '画像生成'
    }
    return titles[type] || type
}

function getStatusText(status) {
    const texts = {
        'pending': '待機中',
        'processing': '処理中',
        'completed': '完了',
        'failed': '失敗'
    }
    return texts[status] || status
}

function formatTime(isoString) {
    return new Date(isoString).toLocaleString('ja-JP')
}

function viewResult(job) {
    // 結果画面へ遷移
    router.push(`/plans/job/${job.id}`)
}

function retryJob(job) {
    // ジョブ再実行
    // ... 実装
}

let refreshInterval
onMounted(() => {
    loadUserJobs()
    // 定期更新（30秒間隔）
    refreshInterval = setInterval(loadUserJobs, 30000)
})

onUnmounted(() => {
    if (refreshInterval) {
        clearInterval(refreshInterval)
    }
})
</script>

<style scoped>
.tasks-view {
    width: 100%;
    height: 100%;
    padding: 20px 16px;
    box-sizing: border-box;
    overflow: auto;
}

.job-card {
    background: #f8f9fa;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 12px;
    border: 1px solid #e9ecef;
}

.job-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}

.status {
    padding: 4px 8px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
}

.status.pending { background: #fef3cd; color: #664d03; }
.status.processing { background: #cff4fc; color: #055160; }
.status.completed { background: #d1e7dd; color: #0f5132; }
.status.failed { background: #f8d7da; color: #721c24; }

.progress {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 8px;
}

.progress-bar {
    flex: 1;
    height: 8px;
    background: #e9ecef;
    border-radius: 4px;
    overflow: hidden;
}

.progress-fill {
    height: 100%;
    background: #0d6efd;
    transition: width 0.3s ease;
}

.btn-primary, .btn-secondary {
    padding: 8px 16px;
    border-radius: 6px;
    border: none;
    font-weight: 600;
    cursor: pointer;
}

.btn-primary {
    background: #0d6efd;
    color: white;
}

.btn-secondary {
    background: #6c757d;
    color: white;
}
</style>
```

### データベーススキーマ

#### Firestore コレクション設計
```javascript
// /jobs/{job_id} ドキュメント構造
{
  id: "job_12345",
  user_id: "user_789",
  type: "plan_generation",
  status: "pending|processing|completed|failed",
  params: {
    keyword: "温泉旅行",
    travel_type: "リラックス派",
    user_preferences: {
      // 将来的なパーソナライゼーション
    }
  },
  result: {
    plans: [
      {
        id: 1,
        title: "草津温泉 癒しの旅",
        description: "...",
        itinerary: [...],
        places: [...],
        route_info: {...}
      }
      // ... 他のプラン
    ],
    metadata: {
      generated_model: "gemini-2.0-flash",
      generation_time_ms: 45000,
      agent_version: "1.0.0"
    }
  },
  error: null,
  progress: 0,
  created_at: "2025-09-13T10:30:00Z",
  updated_at: "2025-09-13T10:32:15Z",
  completed_at: "2025-09-13T10:32:15Z"
}
```

### 段階的実装プラン

#### フェーズ1: 基本機能（Week 1-2）
- [x] ジョブ管理システム実装
- [ ] 非同期API エンドポイント作成
- [ ] フロントエンドポーリング機能
- [ ] 基本通知システム
- [ ] タスク管理画面更新

#### フェーズ2: 永続化対応（Week 3）
- [ ] Firestore ジョブ永続化
- [ ] サーバー再起動耐性
- [ ] ジョブ履歴管理
- [ ] エラー処理強化

#### フェーズ3: UX向上（Week 4）
- [ ] リアルタイムプログレス表示
- [ ] ジョブキャンセル機能
- [ ] バッチプラン生成
- [ ] 画像生成対応準備

#### フェーズ4: 高度機能（Future）
- [ ] WebSocket/SSE移行
- [ ] Firestore リアルタイムリスナー
- [ ] プッシュ通知対応
- [ ] ジョブ優先度制御

### 期待される効果

#### UX改善
- ✅ **待機時間の解放**: ユーザーは生成中も他の機能を利用可能
- ✅ **複数プラン同時生成**: 並行処理により効率向上
- ✅ **進捗の可視化**: リアルタイムな状態確認
- ✅ **セッション継続**: ページリロードや一時離脱に対応

#### 技術的メリット
- ✅ **スケーラビリティ**: 将来の機能拡張に柔軟対応
- ✅ **信頼性向上**: エラー処理・リトライ機能
- ✅ **パフォーマンス**: サーバーリソースの効率利用
- ✅ **監視可能性**: ジョブ実行ログ・メトリクス収集

#### 将来拡張性
- ✅ **画像生成統合**: 同じフレームワークで画像生成ジョブ対応
- ✅ **バッチ処理**: 複数ユーザーのプラン一括生成
- ✅ **API外部公開**: 非同期ジョブAPIの外部提供
- ✅ **分散処理**: 複数サーバーでのジョブ処理分散

### まとめ

本実装方針により、Issue #199の要求事項を満たしつつ、将来の機能拡張に対応可能な基盤を構築できます。段階的な実装アプローチにより、リスクを最小化しながら着実に非同期処理システムを導入できます。

フェーズ1の基本実装だけでも、現在のUX問題の大部分は解決され、その後の拡張により更なる価値を提供できます。