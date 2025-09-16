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

function imageFor(p){
  if (!p) return placeholderForTitle('')
  if (p.image_base64) {
    const mime = p.image_mime_type || 'image/png'
    return `data:${mime};base64,${p.image_base64}`
  }
  return p.image_url || p.hero_image || placeholderForTitle(p.title||'')
}

function bgFor(p){
  const src = imageFor(p)
  // Wrap with url() for CSS var usage
  return `url(${src})`
}

function placeholderForTitle(title){
  const key = encodeURIComponent((title || 'travel landscape').toString())
  return `https://source.unsplash.com/featured/600x400?${key}`
}

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
  <button @click="openTravelDayChat" class="chat-btn" aria-label="当日チャットを開く">
          <v-icon name="chat" :size="20" color="#065f46" aria-label="チャット" />
          当日チャットを開く
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
        :style="{ '--bg-img': bgFor(p) }"
        :class="{ active: isActivePlan(p.id) }" 
        @click="openDetail(p)" 
        role="button" 
        :aria-label="p.title"
      >
        <div class="card-overlay"></div>
        <div class="corner-actions">
          <button 
            @click="toggleActivePlan($event, p)" 
            class="toggle-btn" 
            :class="{ active: isActivePlan(p.id) }"
            :aria-label="isActivePlan(p.id) ? '旅行当日モードを解除' : '旅行当日モードを有効化'"
            :title="isActivePlan(p.id) ? '旅行当日モードを解除' : '旅行当日モードを有効化'"
            :aria-pressed="isActivePlan(p.id) ? 'true' : 'false'"
          >
            <v-icon name="chat-outline" :size="16" aria-label="トグル" />
          </button>
        </div>
        <div class="card-content">
          <div class="card-text-wrap">
            <h2 class="title">{{ p.title || '無題プラン' }}</h2>
            <p class="meta">{{ p.created_at || '' }}</p>
          </div>
        </div>
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
  background: #ffffff;
  color: #065f46; /* dark green text */
  border: 2px solid rgba(255, 255, 255, 0.9);
  border-radius: 14px;
  padding: 14px 22px;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.25s ease;
  text-shadow: none;
  min-height: 52px;
  box-shadow: 0 6px 16px rgba(0,0,0,0.25), 0 0 0 2px rgba(255,255,255,0.4) inset;
}

.chat-btn:hover {
  background: #f8fafc;
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(0,0,0,0.28), 0 0 0 2px rgba(255,255,255,0.5) inset;
}

.chat-btn:active {
  transform: translateY(0);
  box-shadow: 0 4px 12px rgba(0,0,0,0.2), 0 0 0 2px rgba(255,255,255,0.5) inset;
}

.chat-btn:focus-visible {
  outline: 3px solid rgba(255,255,255,0.9);
  outline-offset: 2px;
}

.chat-btn svg {
  width: 20px;
  height: 20px;
  filter: none;
  color: #065f46;
  stroke: currentColor;
}

.state { padding:20px; text-align:center; color:#374151; }
.state.error { color:#b91c1c; }
.cards { 
  display: grid; 
  grid-template-columns: repeat(auto-fill, minmax(240px,1fr)); 
  gap: 14px; 
  justify-content: center; /* Center the grid items */
  max-width: 100%; /* Prevent horizontal scrolling */
  margin: 0 auto; /* Center the grid container */
  width: 100%;
  padding: 0 8px; /* 左右のガターを明示的に確保 */
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
  padding: 0 8px; /* モバイルでも左右対称の余白を維持 */
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
  padding: 0 6px; /* 極小画面では少し細めの余白 */
  }
}

.card { 
  position: relative;
  isolation: isolate;
  background: #ddd;
  border-radius: 18px;
  overflow: hidden;
  height: 180px;
  cursor: pointer;
  box-shadow: 0 6px 14px rgba(0,0,0,0.08);
  transition: transform .2s ease, box-shadow .2s ease;
  /* カード端のクリップ対策としてコンテナ内に少し収める */
  margin-left: 2px;
  margin-right: 2px;
}
.card::before{
  content:"";
  position:absolute; inset:0;
  background: var(--bg-img) center/cover no-repeat;
  filter: brightness(1) saturate(1.05);
  transform: scale(1.02);
  transition: transform .6s ease;
}
.card-overlay{ position:absolute; inset:0; background:linear-gradient(to top, rgba(0,0,0,0.65), rgba(0,0,0,0.1)); mix-blend-mode:multiply; z-index:1; }
.card:hover{ transform: translateY(-2px); box-shadow: 0 10px 24px rgba(0,0,0,0.12); }
.card:hover::before{ transform: scale(1.06); }
.card-content{ position:absolute; z-index:2; bottom:12px; left:14px; right:14px; color:#fff; display:flex; flex-direction:column; gap:6px; }
.card-text-wrap{ background: rgba(0,0,0,0.45); backdrop-filter: blur(2px); padding: 8px 10px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
.card .title{ font-size:16px; font-weight:700; margin:0; letter-spacing:.2px; }
.card .meta{ font-size:12px; opacity:.9; margin: 2px 0 0; }
.card-content .title, .card-content .meta { color: #fff !important; }
.corner-actions{ position:absolute; z-index:3; top:10px; right:10px; display:flex; gap:6px; }

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
  border: 1.5px solid rgba(255,255,255,0.95);
  background: #ffffff;
  color: #065f46; /* dark green */
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  padding: 8px 12px;
  min-height: 36px;
  min-width: 44px; /* touch target */
  box-shadow: 0 4px 12px rgba(0,0,0,0.18);
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
  
  .toggle-btn { padding: 10px 14px; min-height: 44px; }
  
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
  background: #f8fafc;
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(0,0,0,0.22);
}
.toggle-btn:active { transform: translateY(0); }
.toggle-btn svg { width: 16px; height: 16px; stroke: currentColor; }
/* .toggle-label removed as icon-only */
.toggle-btn.active {
  background: linear-gradient(135deg, #10b981, #059669);
  color: #ffffff;
  border-color: rgba(255,255,255,0.95);
}
.toggle-btn.active:hover { filter: brightness(1.05); }

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
