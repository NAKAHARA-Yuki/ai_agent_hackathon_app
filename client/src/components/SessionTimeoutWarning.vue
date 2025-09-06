<template>
  <div v-if="showWarning" class="session-warning">
    <div class="warning-content">
      <h3>⚠️ セッション期限が近づいています</h3>
      <p>あと{{ Math.ceil(timeRemaining / 60) }}分でセッションが切れます。</p>
      <p>作業を継続する場合は「延長」をクリックしてください。</p>
      <div class="warning-actions">
        <button @click="extendSession" class="primary">延長</button>
        <button @click="dismissWarning" class="secondary">閉じる</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/authStore'

const auth = useAuthStore()
const showWarning = ref(false)
const timeRemaining = ref(0)
let warningTimer = null
let updateTimer = null

// セッション期限切れ警告を表示するタイミング（秒）
const WARNING_THRESHOLD = 5 * 60 // 5分前
const DISMISS_COOLDOWN_MS = 60 * 1000 // 再表示までのクールダウン 1分
const POLL_INTERVAL_MS = 30 * 1000 // 残り時間チェック間隔 30秒

const shouldShowWarning = computed(() => {
  return auth.isAuthenticated && timeRemaining.value > 0 && timeRemaining.value <= WARNING_THRESHOLD
})

function updateTimeRemaining() {
  if (!auth.isAuthenticated) {
    showWarning.value = false
    return
  }
  
  timeRemaining.value = auth.getTokenTimeRemaining()
  
  if (shouldShowWarning.value && !showWarning.value) {
    showWarning.value = true
  } else if (!shouldShowWarning.value && showWarning.value) {
    showWarning.value = false
  }
}

function extendSession() {
  // セッション延長（実際にはログイン状態を確認）
  auth.refreshMe().then(() => {
    showWarning.value = false
    // 成功メッセージを表示（コンソールまたはトースト）
    console.info('セッションを確認しました。')
  }).catch(() => {
    // 延長失敗の場合はユーザーに通知し、ログアウト
    alert('セッションの延長に失敗しました。再度ログインしてください。')
    auth.logout('expired')
  })
}

function dismissWarning() {
  showWarning.value = false
  // クールダウン後に再チェック
  setTimeout(() => {
    updateTimeRemaining()
  }, DISMISS_COOLDOWN_MS)
}

function startMonitoring() {
  // 指定間隔ごとに残り時間をチェック
  updateTimer = setInterval(updateTimeRemaining, POLL_INTERVAL_MS)
  // 初回チェック
  updateTimeRemaining()
}

function stopMonitoring() {
  if (updateTimer) {
    clearInterval(updateTimer)
    updateTimer = null
  }
  if (warningTimer) {
    clearTimeout(warningTimer)
    warningTimer = null
  }
}

onMounted(() => {
  startMonitoring()
})

onUnmounted(() => {
  stopMonitoring()
})
</script>

<style scoped>
.session-warning {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 1000;
  background: #fff;
  border: 2px solid #f59e0b;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  max-width: 350px;
  animation: slideIn 0.3s ease-out;
}

.warning-content {
  padding: 16px;
}

.warning-content h3 {
  margin: 0 0 8px 0;
  color: #f59e0b;
  font-size: 16px;
}

.warning-content p {
  margin: 4px 0;
  font-size: 14px;
  color: #374151;
}

.warning-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
}

.warning-actions button {
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
}

.warning-actions .primary {
  background: #3b82f6;
  color: white;
}

.warning-actions .primary:hover {
  background: #2563eb;
}

.warning-actions .secondary {
  background: #e5e7eb;
  color: #374151;
}

.warning-actions .secondary:hover {
  background: #d1d5db;
}

@keyframes slideIn {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}
</style>