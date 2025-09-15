<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { useActivePlanStore } from '@/stores/activePlanStore'
import { listPlans } from '@/services/apiClient'
import BackButton from '@/components/BackButton.vue'
import Toast from '@/components/Toast.vue'

const auth = useAuthStore()
const activePlanStore = useActivePlanStore()
const router = useRouter()
const loading = ref(false)
const items = ref([])
const error = ref('')
const toast = ref('')

async function fetchPlans() {
  loading.value = true
  error.value = ''
  try {
  const j = await listPlans(auth.authHeader())
    items.value = Array.isArray(j.items) ? j.items.sort((a,b) => (b.created_at||'') > (a.created_at||'') ? 1 : -1) : []
    
    // Fetch active plan status
    await activePlanStore.fetchActivePlan()
  } catch (e) {
    error.value = '読み込みに失敗しました'
  } finally { loading.value = false }
}

function openDetail(it){
  // Navigate to plan detail view
  router.push({ name: 'plan-detail', params: { id: it.id } })
}

async function toggleActivePlan(event, plan) {
  event.stopPropagation() // Prevent opening detail view
  try {
    if (activePlanStore.activePlanId === plan.id) {
      await activePlanStore.deactivatePlan()
      toast.value = 'プランを無効化しました'
    } else {
      await activePlanStore.activatePlan(plan.id)
      toast.value = 'プランを有効化しました'
    }
  } catch (e) {
    toast.value = 'エラーが発生しました: ' + (e.message || '不明なエラー')
  }
}

function openTravelDayChat() {
  if (activePlanStore.activePlanId) {
    router.push({ name: 'travel-day-chat', params: { id: activePlanStore.activePlanId } })
  }
}

const isActivePlan = computed(() => (planId) => {
  return activePlanStore.activePlanId === planId
})

onMounted(fetchPlans)
</script>

<template>
  <main class="plans-list">
    <header class="header">
      <BackButton :icon-only="true" icon="chevron-left" label="戻る" :fallback-name="'main'" />
      <h1>保存したプラン</h1>
    </header>
    
    <!-- Active Plan Quick Access -->
    <div v-if="activePlanStore.isActive" class="active-plan-banner">
      <div class="banner-content">
        <div class="banner-info">
          <div class="banner-title">{{ activePlanStore.activePlanTitle }}</div>
          <div class="banner-subtitle">旅行当日モード中</div>
        </div>
        <button @click="openTravelDayChat" class="chat-btn" aria-label="旅行当日チャット">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
          </svg>
          チャット
        </button>
      </div>
    </div>
    
    <div v-if="loading" class="state">読み込み中...</div>
    <div v-else-if="error" class="state error">{{ error }}</div>
    <div v-else class="cards" v-auto-animate>
      <div 
        v-for="p in items" 
        :key="p.id" 
        class="card" 
        :class="{ active: isActivePlan(p.id) }" 
        @click="openDetail(p)" 
        role="button" 
        :aria-label="p.title"
      >
        <div class="card-header">
          <div class="title">{{ p.title || '無題プラン' }}</div>
          <button 
            @click="toggleActivePlan($event, p)" 
            class="toggle-btn" 
            :class="{ active: isActivePlan(p.id) }"
            :aria-label="isActivePlan(p.id) ? 'プランを無効化' : 'プランを有効化'"
          >
            <svg v-if="isActivePlan(p.id)" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
            </svg>
          </button>
        </div>
        <div class="meta">{{ p.created_at || '' }}</div>
        <div v-if="isActivePlan(p.id)" class="active-badge">旅行当日モード</div>
      </div>
      <p v-if="!items.length" class="empty">まだ保存されたプランはありません。</p>
    </div>
    <Toast v-model="toast" />
  </main>
</template>

<style scoped>
.plans-list { 
  display: flex; 
  flex-direction: column; 
  gap: 12px; 
  width: 100%; 
  padding: 0 0 20px; /* 左右のパディングを削除。App.vueのcontentが既にパディングを提供 */
  box-sizing: border-box;
  min-height: 100%;
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden; /* 横スクロール完全に無効化 */
  max-width: 100vw; /* ビューポート幅を超えないよう制限 */
  /* より厳密な幅制限とオーバーフロー制御 */
  contain: layout style;
  /* 確実にコンテナ幅を制限 */
  margin: 0 auto;
  position: relative;
}

/* モバイル対応: より適切なパディングとスクロール */
@media (max-width: 768px) {
  .plans-list {
    padding: 0 0 24px; /* 左右のパディングを削除。App.vueのcontentが既にパディングを提供 */
    gap: 12px;
    /* スクロール領域の最適化 */
    -webkit-overflow-scrolling: touch;
    overscroll-behavior: contain;
    /* 確実にモバイルでビューポート幅制限 */
    max-width: calc(100vw - 16px); /* App.vueの8px * 2を考慮 */
    width: calc(100vw - 16px);
  }
}

@media (max-width: 480px) {
  .plans-list {
    padding: 0 0 20px; /* 左右のパディングを削除 */
    gap: 10px;
    /* 非常に小さな画面でのビューポート制限 */
    max-width: calc(100vw - 8px); /* App.vueの4px * 2を考慮 */
    width: calc(100vw - 8px);
  }
}

.header { 
  display: flex; 
  align-items: center; 
  gap: 12px; 
  background: rgba(255,255,255,0.9); 
  padding: 8px 12px; /* 内部パディングは維持 */
  border-radius: 12px; 
  box-shadow: 0 4px 10px rgba(0,0,0,0.05); 
  margin-bottom: 8px;
  flex-shrink: 0; /* ヘッダーの収縮を防ぐ */
  /* 確実にヘッダー幅を制限 */
  max-width: 100%;
  width: 100%;
  box-sizing: border-box;
  overflow: hidden; /* ヘッダーコンテンツのオーバーフロー防止 */
}

.header h1 { 
  font-size: 18px; 
  margin: 0; 
  flex: 1; 
  /* タイトルのオーバーフロー制御 */
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

/* モバイル対応: ヘッダーサイズ調整 */
@media (max-width: 768px) {
  .header {
    padding: 12px 16px; /* モバイルでは適度な内部パディングを維持 */
    gap: 12px;
    border-radius: 10px;
    margin-bottom: 12px;
  }
  
  .header h1 {
    font-size: 17px;
  }
}

@media (max-width: 480px) {
  .header {
    padding: 10px 14px;
    gap: 10px;
  }
  
  .header h1 {
    font-size: 16px;
  }
}

/* Active Plan Banner - More prominent design with mobile fixes */
.active-plan-banner {
  background: linear-gradient(135deg, #10b981, #059669);
  color: white;
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 8px 20px rgba(16, 185, 129, 0.4);
  margin-bottom: 16px;
  border: 2px solid rgba(255, 255, 255, 0.2);
  position: relative;
  overflow: hidden;
  /* Prevent clipping on mobile */
  min-height: 120px;
  width: 100%;
  max-width: 100%; /* 幅制限追加 */
  box-sizing: border-box;
}

.active-plan-banner::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(45deg, transparent 40%, rgba(255,255,255,0.1) 50%, transparent 60%);
  animation: shimmer 2s infinite;
}

@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

/* Performance optimization and accessibility */
@media (prefers-reduced-motion: reduce) {
  .active-plan-banner::before {
    animation-play-state: paused !important;
  }
}

.active-plan-banner:hover::before {
  animation-play-state: paused;
}

.banner-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: relative;
  z-index: 1;
}

.banner-info {
  flex: 1;
  min-width: 0; /* フレックスアイテムの縮小を許可 */
  overflow: hidden; /* オーバーフロー制御 */
}

.banner-title {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 6px;
  text-shadow: 0 1px 2px rgba(0,0,0,0.1);
  /* 長いタイトルのオーバーフロー制御 */
  word-break: break-word;
  overflow-wrap: break-word;
  max-width: 100%;
}

.banner-subtitle {
  font-size: 14px;
  opacity: 0.9;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 6px;
}

.banner-subtitle::before {
  content: "🗓️";
  font-size: 16px;
}

.chat-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.25);
  color: white;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 14px;
  padding: 12px 20px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  text-shadow: 0 1px 2px rgba(0,0,0,0.1);
  min-height: 48px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}

.chat-btn:hover {
  background: rgba(255, 255, 255, 0.35);
  border-color: rgba(255, 255, 255, 0.5);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}

.chat-btn:active {
  transform: translateY(0);
}

.chat-btn svg {
  width: 20px;
  height: 20px;
  filter: drop-shadow(0 1px 1px rgba(0,0,0,0.1));
}

.state { padding:20px; text-align:center; color:#374151; }
.state.error { color:#b91c1c; }
.cards { 
  display: grid; 
  grid-template-columns: repeat(auto-fill, minmax(220px,1fr)); 
  gap: 12px; 
  justify-content: center; /* Center the grid items */
  max-width: 100%; /* Prevent horizontal scrolling */
  margin: 0 auto; /* Center the grid container */
  width: 100%;
  overflow-x: hidden; /* 横スクロール無効化 */
  /* より厳密な幅制限 */
  contain: layout;
  /* 確実にカードコンテナを制限 */
  box-sizing: border-box;
}

/* モバイル対応: グリッドレイアウトの最適化 */
@media (max-width: 768px) {
  .cards { 
    grid-template-columns: 1fr; /* 1列レイアウトでより使いやすく */
    gap: 10px;
    max-width: 100%; /* 横スクロール防止 */
    width: 100%;
    justify-items: stretch; /* カードを全幅に拡張 */
    overflow-x: hidden; /* 確実に横スクロール無効 */
    /* Prevent cards from clipping on the left */
    margin: 0;
    padding: 0;
    /* より厳密な制約 */
    min-width: 0;
    /* カードが確実にコンテナ内に収まるようにする */
    contain: layout strict;
  }
}

@media (min-width: 769px) and (max-width: 1024px) {
  .cards { 
    grid-template-columns: repeat(auto-fill, minmax(180px,1fr)); 
  }
}

/* 非常に小さな画面用の調整 */
@media (max-width: 480px) {
  .cards { 
    gap: 8px;
  }
}

.card { 
  background: var(--color-surface); 
  border: 1px solid var(--color-border); 
  border-radius: 14px; 
  padding: 14px 16px; 
  box-shadow: 0 6px 14px rgba(0,0,0,0.05); 
  display: flex; 
  flex-direction: column; 
  gap: 8px; 
  cursor: pointer; 
  position: relative;
  transition: all 0.2s ease;
  min-height: 100px;
  width: 100%; /* 全幅使用 */
  max-width: 100%; /* 幅制限 */
  box-sizing: border-box; /* パディングを含めてサイズ計算 */
  /* コンテンツオーバーフロー制御の強化 */
  overflow: hidden;
  contain: layout style;
  /* さらに厳密なカード幅制限 */
  min-width: 0; /* フレックスアイテムの最小幅をリセット */
}

.card:active { transform: translateY(1px); }

.card.active {
  /* Increase min-height for active cards with badges to prevent crushing */
  min-height: 130px;
  border-color: #10b981;
  box-shadow: 0 6px 20px rgba(16, 185, 129, 0.2);
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.card .title { 
  font-weight: 600; 
  font-size: 14px; 
  color: var(--color-text); 
  line-height: 1.3; 
  flex: 1;
  word-break: break-word;
  /* 長いテキストのオーバーフロー制御強化 */
  overflow-wrap: break-word;
  hyphens: auto;
  max-width: 100%;
}

.toggle-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #9ca3af;
  transition: all 0.2s ease;
  flex-shrink: 0;
  min-width: 24px;
}

/* モバイル対応: カードとボタンの改善 */
@media (max-width: 768px) {
  .card {
    padding: 16px 18px;
    border-radius: 12px;
    min-height: 120px;
    /* タッチスクロール改善 */
    touch-action: manipulation;
  }
  
  .card.active {
    /* Increase min-height for active cards with badges to prevent crushing */
    min-height: 160px;
  }
  
  .card .title {
    font-size: 15px;
    line-height: 1.4;
  }
  
  .toggle-btn {
    width: 44px;
    height: 44px;
    min-width: 44px;
    /* WCAG AA準拠の44px最小タッチターゲット */
  }
  
  .card-header {
    gap: 14px;
  }
}

@media (max-width: 480px) {
  .card {
    padding: 14px 16px;
    min-height: 110px;
  }
  
  .card.active {
    /* Increase min-height for active cards with badges to prevent crushing */
    min-height: 150px;
  }
  
  .card .title {
    font-size: 14px;
  }
  
  .toggle-btn {
    width: 32px;
    height: 32px;
    min-width: 32px;
  }
  
  .card-header {
    gap: 12px;
  }
}

.toggle-btn:hover {
  background: #f3f4f6;
  color: #6b7280;
}

.toggle-btn.active {
  color: #10b981;
}

.toggle-btn.active:hover {
  background: #ecfdf5;
}

.toggle-btn svg {
  width: 16px;
  height: 16px;
}

.card .meta { font-size:11px; color:#6b7280; }

.active-badge {
  background: linear-gradient(135deg, #10b981, #059669);
  color: white;
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 10px;
  font-weight: 600;
  align-self: flex-start;
  margin-top: 8px;
  box-shadow: 0 2px 6px rgba(16, 185, 129, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.2);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  animation: pulse 2s infinite;
  flex-shrink: 0; /* Prevent the badge from shrinking */
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.05); }
}

/* Accessibility: Respect reduced motion preferences */
@media (prefers-reduced-motion: reduce) {
  .active-badge {
    animation-play-state: paused !important;
  }
}

.empty { 
  text-align: center; 
  padding: 30px 10px; 
  color: #6b7280; 
  grid-column: 1/-1; 
  justify-self: center; /* Center the empty message */
  max-width: 300px; /* Limit width for better readability */
}

@media (max-width: 600px){ 
  .cards { 
    grid-template-columns: 1fr; /* 既に上で設定済みだが、後方互換性のため保持 */
  } 
  
  .active-plan-banner {
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 16px;
    /* Ensure proper height on mobile to prevent clipping */
    min-height: 140px;
  }
  
  .banner-content {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
  
  .chat-btn {
    align-self: stretch;
    justify-content: center;
    padding: 12px 20px;
    font-size: 15px;
    min-height: 48px; /* タッチフレンドリーなサイズ */
    border-radius: 12px;
    width: 100%;
    box-sizing: border-box;
  }
}

/* さらに小さな画面用の追加調整 */
@media (max-width: 480px) {
  .banner-title {
    font-size: 15px;
  }
  
  .banner-subtitle {
    font-size: 11px;
  }
  
  .chat-btn {
    padding: 12px 20px;
    font-size: 14px;
    min-height: 48px;
  }
}
</style>
