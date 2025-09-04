<script setup>
import { ref, watch, nextTick, computed } from 'vue'
import ChatPanel from '@/components/ChatPanel.vue'
import MapPanel from '@/components/MapPanel.vue'
import BackButton from '@/components/BackButton.vue'
import Toast from '@/components/Toast.vue'
import { useAuthStore } from '@/stores/authStore'
import { createPlan } from '@/services/apiClient'

// エージェントが提案した場所の一覧（{ name, lat, lng, note }）
const places = ref([])
const routeInfo = ref(null) // ルート情報（{ origin, destination }）
const isMapOpen = ref(false)
const overlayMapRef = ref(null)
const lastAssistantText = ref('')
const saving = ref(false)
const saveMsg = ref('') // 旧バーメッセージ（互換）
const toastMsg = ref('')
const auth = useAuthStore()

// 保存UIは「本文がある場合のみ」表示（場所だけ/ルートだけでは非表示）
const canSave = computed(() => {
  const hasText = !!(lastAssistantText.value && String(lastAssistantText.value).trim())
  return hasText && auth.isAuthenticated
})

// チャットの送信イベントでエージェント応答と場所候補を反映
function handleAgentUpdate(payload) {
  // payload: { reply, places?, route_info? }
  if (Array.isArray(payload?.places)) {
    // 緯度経度が無くても、名前でのクエリに利用できるため保持
    places.value = payload.places.slice(0, 50)
  }

  if (payload?.route_info && typeof payload.route_info === 'object' && payload.route_info.origin && payload.route_info.destination) {
    routeInfo.value = payload.route_info
  } else {
    routeInfo.value = null
  }
  if (typeof payload?.reply === 'string') {
    lastAssistantText.value = payload.reply
  }
}

// モバイル全画面マップを開いた直後に再計算（Google Mapsのリサイズ対策）
watch(isMapOpen, async (open) => {
  if (!open) return
  await nextTick()
  // DOM反映待ち + レイアウト確定待ち
  setTimeout(() => {
    try { overlayMapRef.value?.refresh?.() } catch {}
  }, 0)
})

async function onSavePlan() {
  if (saving.value) return
  // タイトルは最初の場所名やルート概要から推定、無ければ日時
  const titleFromRoute = routeInfo.value && routeInfo.value.origin && routeInfo.value.destination
    ? `${routeInfo.value.origin} → ${routeInfo.value.destination}`
    : ''
  const titleFromPlace = places.value && places.value.length ? (places.value[0].name || places.value[0].title || '') : ''
  const fallbackTitle = new Date().toLocaleString('ja-JP', { hour12: false })
  const title = (titleFromPlace || titleFromRoute || `旅行プラン ${fallbackTitle}`).slice(0, 60)

  const payload = {
    title,
    text: lastAssistantText.value || '',
    places: places.value || [],
    route_info: routeInfo.value || null,
  }
  saving.value = true
  saveMsg.value = ''
  try {
  await createPlan(payload, auth.authHeader())
  toastMsg.value = '保存しました'
  } catch (e) {
    console.error('save plan failed', e)
  toastMsg.value = '保存に失敗しました'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <main class="planner">
    <header class="planner-header">
      <BackButton :icon-only="true" icon="home" label="メインへ" :fallback-name="'main'" />
      <button
        v-if="places.length"
        class="open-map-inline"
        type="button"
        @click="isMapOpen = true"
        aria-label="地図を開く"
      >地図を見る</button>
    </header>
    <div class="planner-body">
      <ChatPanel class="chat" @agent-update="handleAgentUpdate" @open-map="isMapOpen = true" />
      <div v-if="canSave" class="save-bar">
        <button class="save-btn" :disabled="saving" @click="onSavePlan">{{ saving ? '保存中…' : 'このプランを保存する' }}</button>
      </div>
    </div>

    <!-- 全画面マップ (モバイル前提) -->
    <div v-if="isMapOpen" class="map-overlay">
      <div class="map-overlay__bar">
        <button class="close" @click="isMapOpen = false" aria-label="地図を閉じる">閉じる ✕</button>
      </div>
      <div class="map-overlay__body">
        <MapPanel ref="overlayMapRef" :places="places" :route-info="routeInfo">
          <template #overlay>
            <div class="map-floating-ui">
              <button class="map-touch-btn" @click="isMapOpen=false" aria-label="閉じる">✕</button>
            </div>
          </template>
        </MapPanel>
      </div>
      <div class="map-overlay__footer">
        <button class="back-to-chat" @click="isMapOpen = false" aria-label="チャットに戻る">チャットに戻る</button>
      </div>
    </div>

    <!-- 右ペイン (デスクトップレガシー) は撤去 -->
    <button
      v-if="places.length && !isMapOpen"
      class="open-map-fab"
      type="button"
      @click="isMapOpen = true"
      aria-label="地図を開く"
  >🗺️</button>
  <Toast v-model="toastMsg" :type="toastMsg.includes('失敗') ? 'error' : 'success'" />
  </main>
  
</template>

<style scoped>
.planner { position: relative; display:flex; flex-direction: column; height:100%; width:100%; overflow:hidden; padding: var(--space-2); box-sizing: border-box; }
.planner-header { display:flex; align-items:center; gap:10px; padding:6px 10px; background: rgba(255,255,255,0.85); backdrop-filter: blur(6px); border-radius: var(--radius-lg); box-shadow: var(--shadow-md); margin-bottom:8px; }
.planner-header .open-map-inline { background: var(--color-text); color:#fff; border:none; border-radius: var(--radius-md); padding:8px 14px; font-weight:600; font-size:14px; min-height: var(--tap-min); }
.planner-body { position:relative; flex:1 1 auto; display:flex; flex-direction:column; min-height:0; background: var(--color-surface); border-radius: var(--radius-lg); box-shadow: var(--shadow-lg); overflow:auto; }
.planner-body .chat { flex:1 1 auto; min-height:0; }
.save-bar { position: sticky; bottom:0; z-index:5; padding:10px 10px 14px; background:linear-gradient(to top, rgba(255,255,255,0.96), rgba(255,255,255,0.55) 45%, transparent); display:flex; gap:10px; align-items:center; }
.save-btn { background: var(--color-accent); color:#fff; border:none; border-radius: var(--radius-md); padding:12px 16px; font-weight:700; font-size:14px; min-height: var(--tap-min); }
.save-btn:hover:not(:disabled){ background: var(--color-accent-hover); }
.save-btn[disabled] { opacity:.65; }
.save-msg { color: var(--color-accent); font-size:.85rem; }

/* 全画面マップ */
.map-overlay { position:fixed; inset:0; z-index:60; background: var(--color-bg); display:flex; flex-direction:column; }
.map-overlay__bar { flex:0 0 auto; display:flex; justify-content:flex-end; padding:8px; background:rgba(255,255,255,0.9); border-bottom:1px solid var(--color-border); }
.map-overlay__bar .close { background: var(--color-text); color:#fff; border:none; border-radius: var(--radius-md); padding:8px 14px; font-weight:700; font-size:14px; }
.map-overlay__body { position:relative; flex:1 1 auto; }
.map-overlay__footer { position:sticky; bottom:0; background:rgba(255,255,255,0.96); border-top:1px solid var(--color-border); padding:10px max(12px, env(safe-area-inset-right)) calc(10px + env(safe-area-inset-bottom)) max(12px, env(safe-area-inset-left)); }
.map-overlay__footer .back-to-chat { width:100%; background: var(--color-text); color:#fff; border:none; border-radius: var(--radius-md); padding:12px; font-weight:700; }

/* フローティング地図ボタン */
.open-map-fab { position:fixed; right: clamp(12px, 3vw, 20px); bottom: calc(18px + env(safe-area-inset-bottom)); width:56px; height:56px; border-radius:20px; background: var(--color-text); color:#fff; font-size:24px; display:flex; align-items:center; justify-content:center; border:none; box-shadow:0 10px 28px rgba(0,0,0,0.25); }
.open-map-fab:active { transform: translateY(1px); }
.map-floating-ui { position:absolute; top:10px; right:10px; display:flex; gap:10px; }

@media (max-width: 600px){
  .planner { padding: var(--space-2); }
  .planner-header { padding:6px 8px; }
  .save-btn { font-size:13px; }
}
</style>
