<script setup>
import { ref, watch, nextTick, computed } from 'vue'
import ChatPanel from '@/components/ChatPanel.vue'
import MapPanel from '@/components/MapPanel.vue'
import BackButton from '@/components/BackButton.vue'
import { useAuthStore } from '@/stores/authStore'

// エージェントが提案した場所の一覧（{ name, lat, lng, note }）
const places = ref([])
const routeInfo = ref(null) // ルート情報（{ origin, destination }）
const isMapOpen = ref(false)
const overlayMapRef = ref(null)
const lastAssistantText = ref('')
const saving = ref(false)
const saveMsg = ref('')
const auth = useAuthStore()

// 保存UIは「本文がある場合のみ」表示（場所だけ/ルートだけでは非表示）
const canSave = computed(() => {
  const hasText = !!(lastAssistantText.value && String(lastAssistantText.value).trim())
  return hasText
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
    const resp = await fetch('/api/plans', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...auth.authHeader() },
      body: JSON.stringify(payload)
    })
    if (!resp.ok) {
      const j = await resp.json().catch(() => ({}))
      throw new Error(j.error || `HTTP ${resp.status}`)
    }
    const data = await resp.json()
    saveMsg.value = '保存しました'
    setTimeout(() => { saveMsg.value = '' }, 3000)
  } catch (e) {
    console.error('save plan failed', e)
    saveMsg.value = '保存に失敗しました'
    setTimeout(() => { saveMsg.value = '' }, 4000)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <main class="planner">
    <section class="left">
  <div class="left-header"><BackButton :icon-only="true" icon="home" label="メインへ" :fallback-name="'main'" /></div>
  <ChatPanel @agent-update="handleAgentUpdate" @open-map="isMapOpen = true" />
  <div v-if="canSave" class="save-bar">
    <button class="save-btn" :disabled="saving" @click="onSavePlan">{{ saving ? '保存中…' : 'このプランを保存する' }}</button>
    <span v-if="saveMsg" class="save-msg">{{ saveMsg }}</span>
  </div>
    </section>
    <section class="right">
      <MapPanel :places="places" :route-info="routeInfo" />
    </section>

    <!-- モバイル: 全画面マップオーバーレイ -->
    <div v-if="isMapOpen" class="map-overlay">
      <div class="map-overlay__bar">
        <button class="close" @click="isMapOpen = false" aria-label="地図を閉じる">閉じる ✕</button>
      </div>
      <div class="map-overlay__body">
  <MapPanel ref="overlayMapRef" :places="places" :route-info="routeInfo" />
      </div>
      <div class="map-overlay__footer">
        <button class="back-to-chat" @click="isMapOpen = false" aria-label="チャットに戻る">チャットに戻る</button>
      </div>
    </div>
  </main>
  
</template>

<style scoped>
.planner {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr;
  gap: 12px;
  height: 100%; /* 親 .content が 100vh-Header のため全高を占有 */
  width: 100%;
  overflow: hidden; /* 外側でスクロールさせない */
}
.left, .right {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 6px 18px rgba(0,0,0,.08);
  overflow: hidden; /* 各ペインの内部で必要に応じてスクロール */
  height: 100%;
}
.left { display:flex; flex-direction: column; }
.left > .chat { flex: 1; min-height: 0; }
.right { position: relative; }
.left-header { position: sticky; top: 0; z-index: 5; padding: 6px; background: rgba(255,255,255,0.92); backdrop-filter: blur(6px); border-bottom: 1px solid #f1f5f9; }
.save-bar { position: sticky; bottom: 0; z-index: 4; padding: 8px 8px 12px; background: linear-gradient(to top, rgba(255,255,255,0.96), rgba(255,255,255,0.6) 40%, transparent); display: flex; gap: 10px; align-items: center; }
.save-btn { background: #0f766e; color: #fff; border: none; border-radius: 10px; padding: 10px 14px; font-weight: 700; }
.save-btn[disabled] { opacity: .7; }
.save-msg { color: #065f46; font-size: .95em; }

/* 全画面マップオーバーレイ */
.map-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  background: #fff;
  display: none; /* デスクトップでは非表示 */
  flex-direction: column;
}
.map-overlay__bar {
  flex: 0 0 auto;
  display: flex;
  justify-content: flex-end;
  padding: 8px;
  background: rgba(255,255,255,0.9);
  border-bottom: 1px solid #e5e7eb;
}
.map-overlay__bar .close {
  background: #111827;
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 8px 12px;
  font-weight: 700;
}
.map-overlay__body {
  position: relative;
  flex: 1 1 auto;
}

.map-overlay__footer {
  position: sticky;
  bottom: 0;
  background: rgba(255,255,255,0.96);
  border-top: 1px solid #e5e7eb;
  padding: 10px max(12px, env(safe-area-inset-right)) calc(10px + env(safe-area-inset-bottom)) max(12px, env(safe-area-inset-left));
}
.map-overlay__footer .back-to-chat {
  width: 100%;
  background: #111827;
  color: #fff;
  border: none;
  border-radius: 10px;
  padding: 12px;
  font-weight: 700;
}

@media (max-width: 960px) {
  .planner { grid-template-columns: 1fr; grid-template-rows: 1fr; }
  /* 通常時は右ペインのマップを非表示 */
  .right { display: none; }
  /* モバイルでのみボタン表示 */
  .open-map-btn { display: inline-flex; align-items: center; gap: 6px; }
  /* モバイルでのみオーバーレイ有効化 */
  .map-overlay { display: flex; }
}
</style>
