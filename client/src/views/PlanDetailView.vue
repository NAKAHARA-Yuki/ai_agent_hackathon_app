<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { planDetail, deletePlan } from '@/services/apiClient'
import Toast from '@/components/Toast.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const plan = ref(null)
const loading = ref(true)
const error = ref('')
const toast = ref('')
const deleting = ref(false)
const showDeleteConfirm = ref(false)
const imageLoadError = ref(false)

const heroImageSrc = computed(() => {
  const p = plan.value
  if (!p) return null
  if (p.image_base64) {
    const mime = p.image_mime_type || 'image/png'
    return `data:${mime};base64,${p.image_base64}`
  }
  return p.image_url || p.hero_image || null
})

async function load(){
  loading.value = true
  error.value = ''
  try {
    const id = route.params.id
    plan.value = await planDetail(id, auth.authHeader())
  } catch(e){ 
    if (e.message && e.message.includes('HTTP 503')) {
      error.value = 'サーバーが混雑しています。時間をおいて再試行してください。'
    } else {
      error.value = '読込に失敗しました'
    }
    console.error(e) 
  } finally { 
    loading.value=false 
  }
}

onMounted(load)

function goBack(){ router.back() }

function startRefinement() {
  const planId = route.params.id
  router.push(`/plans/${planId}/chat`)
}

function confirmDelete() {
  showDeleteConfirm.value = true
}

function cancelDelete() {
  showDeleteConfirm.value = false
}

async function executeDelete() {
  if (deleting.value) return
  
  deleting.value = true
  showDeleteConfirm.value = false
  
  try {
    const planId = route.params.id
    await deletePlan(planId, auth.authHeader())
    toast.value = 'プランを削除しました'
    
    // Navigate back to plans list after a short delay
    setTimeout(() => {
      router.push('/plans')
    }, 1500)
  } catch(e) {
    console.error('Delete error:', e)
    toast.value = 'プランの削除に失敗しました: ' + (e.message || '不明なエラー')
  } finally {
    deleting.value = false
  }
}

// Transport helpers (shared with DetailScreen.vue)
import { transportLabel, transportIcon, formatDuration, formatDistance } from '@/utils/transportHelpers'

function handleImageError() {
  // Use reactive pattern instead of direct DOM manipulation
  imageLoadError.value = true
}
</script>

<template>
  <div class="plan-detail-screen">
    <button class="back" @click="goBack" aria-label="戻る">← 戻る</button>
    <div v-if="loading" class="loading">読み込み中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="plan" class="content">
      <!-- Hero Image Section -->
    <div v-if="heroImageSrc && !imageLoadError" class="hero-image">
        <img 
      :src="heroImageSrc" 
          :alt="plan.title || '旅行プラン画像'"
          @error="handleImageError"
          class="hero-img"
        />
        <div class="hero-overlay">
          <h1 class="hero-title">{{ plan.title }}</h1>
        </div>
      </div>
      
      <!-- Title for plans without image -->
      <h1 v-else class="title">{{ plan.title }}</h1>
      
      <p v-if="plan.summary" class="summary">{{ plan.summary }}</p>
      <div v-if="plan.suggestions && plan.suggestions.length" class="suggestions">
        <h2>候補</h2>
        <ul>
          <li v-for="(s,i) in plan.suggestions" :key="i">
            <strong>{{ s.title }}</strong>
            <span v-if="s.tags && s.tags.length" class="tags"> — {{ s.tags.join(' / ') }}</span>
            <span v-if="s.brief" class="brief"> {{ s.brief }}</span>
          </li>
        </ul>
      </div>
      <div v-if="plan.itinerary && plan.itinerary.length" class="itinerary">
        <h2>日程</h2>
        <div v-for="(d,idx) in plan.itinerary" :key="idx" class="day">
          <h3>Day {{ d.day || (idx+1) }}</h3>
          <ul class="items">
            <li v-for="(it,i2) in d.items" :key="i2">
              <span class="time" v-if="it.time">{{ it.time }}</span>
              <span class="item-title">{{ it.title }}</span>
              <span class="item-detail" v-if="it.detail"> — {{ it.detail }}</span>
              <!-- transport info -->
              <div v-if="it.transport" class="transport">
                <span class="t-icon">{{ transportIcon(it.transport?.mode) }}</span>
                <span class="t-label">{{ transportLabel(it.transport?.mode) }}</span>
                <span v-if="formatDuration(it.transport?.estimated_duration)" class="t-sep">•</span>
                <span v-if="formatDuration(it.transport?.estimated_duration)" class="t-duration">{{ formatDuration(it.transport?.estimated_duration) }}</span>
                <span v-if="formatDistance(it.transport?.distance_km)" class="t-sep">•</span>
                <span v-if="formatDistance(it.transport?.distance_km)" class="t-distance">{{ formatDistance(it.transport?.distance_km) }}</span>
              </div>
            </li>
          </ul>
        </div>
      </div>
      <div v-if="plan.text" class="raw-text">
        <h2>本文</h2>
        <pre>{{ plan.text }}</pre>
      </div>
      <div v-if="plan.places && plan.places.length" class="places">
        <h2>場所</h2>
        <ul>
          <li v-for="(p,i) in plan.places" :key="i">{{ p.name }}<small v-if="p.note"> — {{ p.note }}</small></li>
        </ul>
      </div>
      
      <!-- Action Buttons -->
      <div class="action-buttons">
        <button class="refine-btn" @click="startRefinement" aria-label="プランをブラッシュアップ">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M8 2v4"></path>
            <path d="M16 2v4"></path>
            <rect width="18" height="18" x="3" y="4" rx="2"></rect>
            <path d="M3 10h18"></path>
            <path d="M8 14h.01"></path>
            <path d="M12 14h.01"></path>
            <path d="M16 14h.01"></path>
            <path d="M8 18h.01"></path>
            <path d="M12 18h.01"></path>
          </svg>
          ブラッシュアップ
        </button>
        
        <button 
          class="delete-btn" 
          @click="confirmDelete" 
          :disabled="deleting"
          aria-label="プランを削除"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 6h18"></path>
            <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
            <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
            <line x1="10" x2="10" y1="11" y2="17"></line>
            <line x1="14" x2="14" y1="11" y2="17"></line>
          </svg>
          {{ deleting ? '削除中...' : 'プランを削除' }}
        </button>
      </div>
      
      <!-- Delete Confirmation Dialog -->
      <div v-if="showDeleteConfirm" class="delete-confirm-overlay" @click="cancelDelete">
        <div class="delete-confirm-dialog" @click.stop>
          <div class="dialog-header">
            <h3>プランの削除</h3>
          </div>
          <div class="dialog-content">
            <p>「{{ plan?.title || '無題プラン' }}」を削除しますか？</p>
            <p>この操作は取り消せません。</p>
          </div>
          <div class="dialog-actions">
            <button class="cancel-btn" @click="cancelDelete">キャンセル</button>
            <button class="confirm-delete-btn" @click="executeDelete" :disabled="deleting">
              {{ deleting ? '削除中...' : '削除する' }}
            </button>
          </div>
        </div>
      </div>
    </div>
    <Toast v-model="toast" />
  </div>
</template>

<style scoped>
/* Hero Image Section */
.hero-image {
  position: relative;
  width: 100%;
  max-height: 300px;
  margin: -20px -16px 24px; /* Extend to edges, add bottom margin */
  border-radius: 0 0 20px 20px;
  overflow: hidden;
  box-shadow: 0 8px 24px rgba(0,0,0,0.12);
}

.hero-img {
  width: 100%;
  height: 250px;
  object-fit: cover;
  object-position: center;
  display: block;
}

.hero-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(transparent, rgba(0,0,0,0.7));
  padding: 40px 20px 20px;
  color: white;
}

.hero-title {
  font-size: 24px;
  font-weight: 700;
  margin: 0;
  text-shadow: 0 2px 8px rgba(0,0,0,0.5);
  line-height: 1.2;
}

/* Mobile responsive adjustments for hero image */
@media (max-width: 768px) {
  .hero-image {
    margin: -8px -8px 20px;
    border-radius: 0 0 16px 16px;
  }
  
  .hero-img {
    height: 200px;
  }
  
  .hero-overlay {
    padding: 30px 16px 16px;
  }
  
  .hero-title {
    font-size: 20px;
  }
}

/* 全体: 余白 + 中央寄せカラム。height/overflow排除で二重スクロール崩れ防止 */
/* ヘッダー固定による見切れ防止として top-padding を十分に確保 */
/* フッター固定による見切れ防止として bottom-padding を十分に確保 */
.plan-detail-screen{ 
  padding: calc(80px + env(safe-area-inset-top)) 16px calc(80px + env(safe-area-inset-bottom)); 
  box-sizing:border-box; 
  display:flex; 
  flex-direction:column; 
  gap:20px; 
  max-width:920px; 
  margin:0 auto; 
  width:100%; 
  min-height: 100vh;
  scroll-margin-top: calc(80px + env(safe-area-inset-top));
}

/* モバイル対応: パディングとレイアウトの最適化 */
@media (max-width: 768px) {
  .plan-detail-screen {
    padding: calc(70px + env(safe-area-inset-top)) 8px calc(90px + env(safe-area-inset-bottom));
    gap: 16px;
    max-width: 100%;
    margin: 0;
  }
}
.back{ 
  align-self: flex-start; 
  background: #fff; 
  border: 1px solid #e2e8f0; 
  padding: 6px 12px; /* Reduced padding to make smaller */
  border-radius: 10px; /* Slightly smaller radius */
  cursor: pointer; 
  font-size: 12px; 
  line-height: 1; 
  box-shadow: 0 2px 5px rgba(0,0,0,0.05); 
  transition: background .2s, border-color .2s;
  min-height: 36px; /* Smaller minimum height */
  max-width: 120px; /* Limit maximum width */
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap; /* Prevent text wrapping */
}
.back:hover{ background:#f1f5f9; }
.back:active{ transform: translateY(1px); }

.title{ 
  font-size:22px; 
  font-weight:700; 
  margin:0; 
  letter-spacing:-.5px; 
  line-height:1.25; 
  word-break:break-word; 
}

.summary{ 
  margin:2px 0 4px; 
  font-size:14px; 
  color:#475569; 
  line-height:1.6; 
  word-break:break-word; 
  overflow-wrap:anywhere; 
}

/* モバイル対応: タイトルとサマリーのサイズ調整 */
@media (max-width: 768px) {
  .back {
    padding: 8px 14px; /* Slightly larger on mobile for touch */
    font-size: 13px;
    min-height: 40px; /* Still smaller than before */
    max-width: 100px; /* Smaller max width on mobile */
  }
  
  .title {
    font-size: 20px;
    line-height: 1.3;
  }
  
  .summary {
    font-size: 13px;
    line-height: 1.5;
  }
}

/* セクション共通カード化 */
.content{ 
  display:flex; 
  flex-direction:column; 
  gap:28px; 
  overflow: visible; /* Ensure content sections are not clipped */
  flex: 1; /* Allow content to grow */
}
.content > .suggestions,
.content > .itinerary,
.content > .raw-text,
.content > .places{ 
  background:#fff; 
  border:1px solid #e2e8f0; 
  border-radius:18px; 
  padding:18px 18px 20px; 
  box-shadow:0 4px 12px -4px rgba(15,23,42,0.06); 
}

/* モバイル対応: コンテンツセクションの調整 */
@media (max-width: 768px) {
  .content {
    gap: 20px;
  }
  
  .content > .suggestions,
  .content > .itinerary,
  .content > .raw-text,
  .content > .places {
    border-radius: 12px;
    padding: 14px 16px 16px;
    margin: 0; /* 余白をリセット */
  }
}

h2{ font-size:15px; margin:0 0 10px; font-weight:700; color:#334155; letter-spacing:.2px; }
h3{ font-size:13px; margin:0 0 6px; font-weight:600; color:#0f172a; }

/* 候補リスト */
.suggestions ul{ list-style:none; padding:0; margin:0; display:flex; flex-direction:column; gap:6px; }
.suggestions li{ font-size:13px; line-height:1.45; color:#475569; }
.suggestions .tags{ color:#64748b; font-size:11px; }
.suggestions .brief{ color:#475569; font-size:11px; }

/* 日程 */
.itinerary .day{ 
  background:#f8fafc; 
  border:1px solid #e2e8f0; 
  border-radius:14px; 
  padding:10px 12px 12px; 
  margin:10px 0 12px; 
  overflow: visible; /* Ensure content is not clipped */
}
.itinerary .day:last-child{ margin-bottom:0; }
.itinerary h3{ margin:0 0 6px; font-size:13px; font-weight:700; color:#334155; }
.items{ 
  list-style:none; 
  padding:0; 
  margin:0; 
  display:flex; 
  flex-direction:column; 
  gap:5px; 
  overflow: visible; /* Ensure items are not clipped */
}
.items li{ 
  font-size:13px; 
  line-height:1.4; 
  color:#475569; 
  display:flex; 
  flex-wrap:wrap; 
  gap:6px; 
  overflow: visible; /* Ensure individual items are not clipped */
}
.items .time{ font-weight:600; min-width:52px; color:#0f172a; }

/* Transport info styles (similar to DetailScreen.vue) */
.items .transport { 
  display:flex; 
  align-items:center; 
  gap:6px; 
  width:100%; 
  margin-top:2px; 
  font-size:12px; 
  color:#64748b; 
}
.items .transport .t-icon { font-size:14px; }
.items .transport .t-label { font-weight:500; }
.items .transport .t-duration,
.items .transport .t-distance { font-size:11px; }
.items .transport .t-sep { opacity:.6; }

/* 本文 */
.raw-text pre{ white-space:pre-wrap; font-size:12.5px; line-height:1.55; background:#f1f5f9; padding:12px 14px; border-radius:14px; border:1px solid #e2e8f0; overflow:auto; max-height:480px; scrollbar-width:thin; }
.raw-text pre::-webkit-scrollbar{ height:8px; width:8px; }
.raw-text pre::-webkit-scrollbar-thumb{ background:#cbd5e1; border-radius:4px; }

/* 場所 */
.places ul{ list-style:disc; padding-left:20px; margin:0; display:flex; flex-direction:column; gap:4px; font-size:12.5px; color:#475569; }
.places li small{ color:#64748b; margin-left:2px; }

/* 状態表示 */
.loading, .error{ font-size:13px; color:#64748b; }
.error{ color:#dc2626; }

/* Action Buttons */
.action-buttons { 
  background:#fff; 
  border:1px solid #e2e8f0; 
  border-radius:18px; 
  padding:18px; 
  box-shadow:0 4px 12px -4px rgba(15,23,42,0.06);
  margin-top: 20px;
  margin-bottom: 20px; /* Extra space to prevent footer overlap */
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.refine-btn { 
  display:flex; 
  align-items:center; 
  justify-content:center; 
  gap:8px; 
  width:100%; 
  padding:12px 20px; 
  background:linear-gradient(135deg, #3b82f6, #1d4ed8); 
  color:#fff; 
  border:none; 
  border-radius:12px; 
  font-size:14px; 
  font-weight:600; 
  cursor:pointer; 
  transition:all .2s ease; 
  box-shadow:0 4px 12px rgba(59,130,246,0.3);
  min-height: 44px; /* Touch-friendly size */
}

.refine-btn:hover { 
  background:linear-gradient(135deg, #2563eb, #1e40af); 
  transform:translateY(-1px); 
  box-shadow:0 6px 16px rgba(59,130,246,0.4); 
}

.refine-btn:active { 
  transform:translateY(0); 
  box-shadow:0 2px 8px rgba(59,130,246,0.3); 
}

.refine-btn svg { 
  width:18px; 
  height:18px;
}

.delete-btn { 
  display:flex; 
  align-items:center; 
  justify-content:center; 
  gap:8px; 
  width:100%; 
  padding:12px 20px; 
  background:linear-gradient(135deg, #ef4444, #dc2626); 
  color:#fff; 
  border:none; 
  border-radius:12px; 
  font-size:14px; 
  font-weight:600; 
  cursor:pointer; 
  transition:all .2s ease; 
  box-shadow:0 4px 12px rgba(239,68,68,0.3);
  min-height: 44px; /* Touch-friendly size */
}

.delete-btn:hover:not(:disabled) { 
  background:linear-gradient(135deg, #dc2626, #b91c1c); 
  transform:translateY(-1px); 
  box-shadow:0 6px 16px rgba(239,68,68,0.4); 
}

.delete-btn:active:not(:disabled) { 
  transform:translateY(0); 
  box-shadow:0 2px 8px rgba(239,68,68,0.3); 
}

.delete-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.delete-btn svg { 
  width:18px; 
  height:18px;
}

/* Delete Confirmation Dialog */
.delete-confirm-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 16px;
}

.delete-confirm-dialog {
  background: white;
  border-radius: 16px;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
  max-width: 400px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
}

.dialog-header {
  padding: 20px 20px 0;
  border-bottom: 1px solid #e2e8f0;
}

.dialog-header h3 {
  margin: 0 0 16px;
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
}

.dialog-content {
  padding: 20px;
  color: #6b7280;
  line-height: 1.6;
}

.dialog-content p {
  margin: 0 0 12px;
}

.dialog-content p:last-child {
  margin-bottom: 0;
  font-size: 14px;
}

.dialog-actions {
  padding: 16px 20px 20px;
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.cancel-btn, .confirm-delete-btn {
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  min-height: 40px;
  border: none;
}

.cancel-btn {
  background: #f3f4f6;
  color: #374151;
}

.cancel-btn:hover {
  background: #e5e7eb;
}

.confirm-delete-btn {
  background: #ef4444;
  color: white;
}

.confirm-delete-btn:hover:not(:disabled) {
  background: #dc2626;
}

.confirm-delete-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* モバイル対応: アクションボタンの調整 */
@media (max-width: 768px) {
  .action-buttons {
    border-radius: 12px;
    padding: 14px;
    margin-bottom: 24px;
    gap: 10px;
  }
  
  .refine-btn, .delete-btn {
    padding: 14px 24px;
    font-size: 15px;
    min-height: 48px;
    border-radius: 10px;
  }
  
  .delete-confirm-overlay {
    padding: 12px;
  }
  
  .delete-confirm-dialog {
    border-radius: 12px;
  }
  
  .dialog-header {
    padding: 16px 16px 0;
  }
  
  .dialog-header h3 {
    font-size: 16px;
  }
  
  .dialog-content {
    padding: 16px;
    font-size: 14px;
  }
  
  .dialog-actions {
    padding: 12px 16px 16px;
    flex-direction: column-reverse;
  }
  
  .cancel-btn, .confirm-delete-btn {
    width: 100%;
    min-height: 44px;
  }
}

@media (min-width:640px){
  .title{ font-size:26px; }
  .summary{ font-size:15px; }
  h2{ font-size:16px; }
  .raw-text pre{ font-size:13px; }
}
</style>
