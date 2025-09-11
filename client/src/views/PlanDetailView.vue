<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const plan = ref(null)
const loading = ref(true)
const error = ref('')

async function load(){
  loading.value = true
  error.value = ''
  try {
    const id = route.params.id
    const resp = await fetch(`/api/plans/${id}`, { headers:{ 'Content-Type':'application/json', ...(auth.authHeader()||{}) } })
    if(!resp.ok){ throw new Error('HTTP '+resp.status) }
    plan.value = await resp.json()
  } catch(e){ error.value = '読込に失敗しました'; console.error(e) } finally { loading.value=false }
}

onMounted(load)

function goBack(){ router.back() }

function startRefinement() {
  const planId = route.params.id
  router.push(`/plans/${planId}/chat`)
}
</script>

<template>
  <div class="plan-detail-screen">
    <button class="back" @click="goBack" aria-label="戻る">← 戻る</button>
    <div v-if="loading" class="loading">読み込み中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="plan" class="content">
      <h1 class="title">{{ plan.title }}</h1>
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
      
      <!-- Refinement Button -->
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
      </div>
    </div>
  </div>
</template>

<style scoped>
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
  align-self:flex-start; 
  background:#fff; 
  border:1px solid #e2e8f0; 
  padding:8px 16px; 
  border-radius:12px; 
  cursor:pointer; 
  font-size:12px; 
  line-height:1; 
  box-shadow:0 2px 5px rgba(0,0,0,0.05); 
  transition:background .2s,border-color .2s;
  min-height: 44px; /* Touch-friendly minimum size */
  display: flex;
  align-items: center;
  gap: 4px;
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
    padding: 10px 18px;
    font-size: 13px;
    min-height: 48px; /* より大きなタッチターゲット */
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

/* モバイル対応: アクションボタンの調整 */
@media (max-width: 768px) {
  .action-buttons {
    border-radius: 12px;
    padding: 14px;
    margin-bottom: 24px;
  }
  
  .refine-btn {
    padding: 14px 24px;
    font-size: 15px;
    min-height: 48px;
    border-radius: 10px;
  }
}

@media (min-width:640px){
  .title{ font-size:26px; }
  .summary{ font-size:15px; }
  h2{ font-size:16px; }
  .raw-text pre{ font-size:13px; }
}
</style>
