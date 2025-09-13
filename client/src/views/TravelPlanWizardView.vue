<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { useRouter } from 'vue-router'
import InputScreen from '@/components/InputScreen.vue'
import LoadingScreen from '@/components/LoadingScreen.vue'
import SuggestionScreen from '@/components/SuggestionScreen.vue'
import DetailScreen from '@/components/DetailScreen.vue'
import { useAuthStore } from '@/stores/authStore'
import { createPlan } from '@/services/apiClient'

const router = useRouter()

const currentView = ref('input') // 'input' | 'loading' | 'suggestions' | 'detail'
const travelPlans = ref([])
const selectedPlan = ref(null)
const saving = ref(false)
const auth = useAuthStore()
const lastKeyword = ref('') // Store the last used keyword for regeneration

async function handleCreatePlan(keyword) {
  if (!keyword || currentView.value !== 'input') return
  
  // Store the keyword for potential regeneration
  lastKeyword.value = keyword
  
  currentView.value = 'loading'
  try {
    // /api/generate_plan を使用
    const resp = await fetch('/api/agent/generate_plan', {
      method: 'POST',
  headers: { 'Content-Type': 'application/json', ...auth.authHeader() },
      body: JSON.stringify({ keyword: String(keyword)})
    })
    if (!resp.ok) throw new Error('Failed to generate plans')
    const data = await resp.json()
    const plans = Array.isArray(data?.plans) ? data.plans.slice(0,3) : []
    const mapped = plans.map((p, i) => {
      const tagsStr = Array.isArray(p?.tags) ? p.tags.map(t => String(t)).join('・') : (typeof p?.tags === 'string' ? p.tags : '')
      return {
        id: i+1,
        title: p?.title || `プラン ${i+1}`,
        tags: tagsStr,
        brief: typeof p?.brief === 'string' ? p.brief : (typeof p?.description === 'string' ? p.description : ''),
        itinerary: Array.isArray(p?.itinerary) ? p.itinerary : [],
        places: Array.isArray(p?.places) ? p.places : [],
        route_info: p?.route_info ?? null,
        text: typeof p?.text === 'string' ? p.text : (typeof p?.brief === 'string' ? p.brief : ''),
        __raw: p,
        __full: data
      }
    })
    travelPlans.value = mapped.length ? mapped : [{ id:1, title: '旅行プラン', tags: '', brief: 'プランを生成できませんでした。', itinerary: [], __full: data }]
    currentView.value = 'suggestions'
  } catch(e){
    console.error('wizard agent error', e)
    // エラーメッセージを表示（モックデータは使用しない）
    alert('旅行プランの生成中にエラーが発生しました。時間をおいて再試行してください。')
    currentView.value = 'input'
  }
}
function handleSelectPlan(p) {
  // 念のため日程/スポット/ルート情報をフォールバックしつつ正規化
  const raw = p && typeof p === 'object' ? p : {}
  const fromRaw = raw.__raw && typeof raw.__raw === 'object' ? raw.__raw : null
  const itinerary = Array.isArray(raw.itinerary)
    ? raw.itinerary
    : (Array.isArray(fromRaw?.itinerary) ? fromRaw.itinerary : [])
  const places = Array.isArray(raw.places)
    ? raw.places
    : (Array.isArray(fromRaw?.places) ? fromRaw.places : [])
  const route_info = raw.route_info ?? (fromRaw?.route_info ?? null)

  selectedPlan.value = {
    id: raw.id,
    title: raw.title || '',
    tags: raw.tags || '',
    brief: raw.brief || '',
    text: raw.text || raw.brief || '',
    itinerary,
    places,
    route_info,
    __raw: raw.__raw || null,
    __full: raw.__full || null,
  }
  currentView.value = 'detail'
}
function handleGoBack() { currentView.value = 'suggestions' }

function handleRefine(plan) {
  // Navigate to the plan chat view for refinement
  // We need to save the plan first, then navigate to the refinement screen
  const tempPlan = {
    title: plan.title,
    text: plan.text || plan.tags || '',
    places: plan.places || [],
    route_info: plan.route_info || null,
    status: 'draft',
    summary: plan.summary || null,
    suggestions: plan.suggestions || [],
    itinerary: plan.itinerary || []
  }
  
  // Create a temporary plan and navigate to refinement
  createPlan(tempPlan, auth.authHeader()).then(response => {
    // Navigate to the plan chat view
    router.push({ name: 'plan-chat', params: { id: response.id } })
  }).catch(e => {
    console.error('Failed to create temp plan for refinement:', e)
  })
}

function handleRegenerate(keyword) {
  // 新しいキーワードで再度プラン生成
  if (!keyword || typeof keyword !== 'string') {
    console.warn('Invalid keyword provided for regeneration:', keyword)
    return
  }
  
  // キーワードの長さチェック
  if (keyword.length > 100) {
    console.warn('Keyword too long for regeneration:', keyword.length)
    return
  }
  
  // 安全性チェック: 危険な文字が含まれていないか
  if (/[<>'"&\x00-\x1F\x7F-\x9F]/.test(keyword)) {
    console.warn('Invalid characters in keyword:', keyword)
    return
  }
  
  // Update the last keyword and switch to loading state
  lastKeyword.value = keyword
  currentView.value = 'loading'
  
  // Call handleCreatePlan but modify flow to skip input validation
  handleCreatePlanForRegeneration(keyword)
}

async function handleCreatePlanForRegeneration(keyword) {
  try {
    const resp = await fetch('/api/agent/generate_plan', {
      method: 'POST',
  headers: { 'Content-Type': 'application/json', ...auth.authHeader() },
  body: JSON.stringify({ keyword: String(keyword) })
    })
    if (!resp.ok) throw new Error('Failed to regenerate plans')
    const data = await resp.json()
    const plans = Array.isArray(data?.plans) ? data.plans.slice(0,3) : []
    const mapped = plans.map((p, i) => {
      const tagsStr = Array.isArray(p?.tags) ? p.tags.map(t => String(t)).join('・') : (typeof p?.tags === 'string' ? p.tags : '')
      return {
        id: i+1,
        title: p?.title || `プラン ${i+1}`,
        tags: tagsStr,
        brief: typeof p?.brief === 'string' ? p.brief : (typeof p?.description === 'string' ? p.description : ''),
        itinerary: Array.isArray(p?.itinerary) ? p.itinerary : [],
        places: Array.isArray(p?.places) ? p.places : [],
        route_info: p?.route_info ?? null,
        text: typeof p?.text === 'string' ? p.text : (typeof p?.brief === 'string' ? p.brief : ''),
        __raw: p,
        __full: data
      }
    })
    travelPlans.value = mapped.length ? mapped : [{ id:1, title: '旅行プラン', tags: '', brief: 'プランを生成できませんでした。', itinerary: [], __full: data }]
    currentView.value = 'suggestions'
  } catch(e){
    console.error('wizard regenerate error', e)
    // エラーメッセージを表示（モックデータは使用しない）
    alert('旅行プランの再生成中にエラーが発生しました。時間をおいて再試行してください。')
    currentView.value = 'suggestions'
  }
}

async function handleConfirm(plan){
  if(saving.value) return
  try {
    saving.value = true
    const full = plan.__full || {}
    const payload = { 
      title: plan.title, 
      text: plan.text || plan.brief || '', 
      places: Array.isArray(plan.places) ? plan.places : [], 
      route_info: plan.route_info || null, 
      status: 'confirmed',
      summary: typeof full.summary === 'string' ? full.summary : null,
      suggestions: Array.isArray(full.suggestions) ? full.suggestions : [],
      itinerary: Array.isArray(plan.itinerary) ? plan.itinerary : []
    }
    await createPlan(payload, auth.authHeader())
    // 保存後ホーム（main）へ遷移 or 予定へ
    window.location.assign('/plans')
  } catch(e){ console.error('wizard save failed', e) } finally { saving.value=false }
}

// --- visualViewport ベースの実高さ制御 ----------------------------------
const viewportHeight = ref(typeof window !== 'undefined' ? (window.visualViewport ? window.visualViewport.height : window.innerHeight) : 0)
const wrapEl = ref(null)

function updateViewportHeight() {
  // iOS Safari のズーム/アドレスバー変動を考慮し visualViewport 優先
  const h = window.visualViewport ? window.visualViewport.height : window.innerHeight
  // ピクセルを整数化（小数→レイアウト抑制）
  viewportHeight.value = Math.round(h)
}

let rafId = null
function scheduleUpdate() {
  if (rafId) cancelAnimationFrame(rafId)
  rafId = requestAnimationFrame(updateViewportHeight)
}

onMounted(() => {
  updateViewportHeight()
  window.addEventListener('resize', scheduleUpdate, { passive: true })
  window.addEventListener('orientationchange', scheduleUpdate, { passive: true })
  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', scheduleUpdate, { passive: true })
    window.visualViewport.addEventListener('scroll', scheduleUpdate, { passive: true })
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', scheduleUpdate)
  window.removeEventListener('orientationchange', scheduleUpdate)
  if (window.visualViewport) {
    window.visualViewport.removeEventListener('resize', scheduleUpdate)
    window.visualViewport.removeEventListener('scroll', scheduleUpdate)
  }
  if (rafId) cancelAnimationFrame(rafId)
})

// 高さは親(main.content) の flex 領域にフィットさせ、ビューポート変動時の再描画安定用に CSS 変数のみ付与
const wrapStyle = computed(() => ({ '--vvh': viewportHeight.value ? Math.round(viewportHeight.value) + 'px' : undefined }))
</script>

<template>
  <div ref="wrapEl" class="wizard-wrap wizard-bg text-slate-900" data-route="travel-wizard" :style="wrapStyle">
    <div class="wizard-inner">
      <InputScreen v-if="currentView==='input'" @create-plan="handleCreatePlan" />
      <LoadingScreen v-else-if="currentView==='loading'" />

      <SuggestionScreen v-else-if="currentView==='suggestions'" :plans="travelPlans" :lastKeyword="lastKeyword" @select-plan="handleSelectPlan" @regenerate="handleRegenerate" />

  <DetailScreen v-else-if="currentView==='detail'" :plan="selectedPlan" @go-back="handleGoBack" @confirm="handleConfirm" @refine="handleRefine" />
    </div>
  </div>
</template>

<style scoped>
/* ルートラッパ: 親 flex 領域にフィット / 余白除去 */
.wizard-wrap { 
  flex:1 1 auto; 
  width:100%; 
  height:100%; 
  display:flex; 
  flex-direction:column; 
  overflow:hidden; 
  position:relative; 
  margin:0; 
  padding-top: env(safe-area-inset-top); 
}
/* 中央固定幅コンテナ (全画面でセンター) */
.wizard-inner { 
  flex:1 1 auto; 
  display:flex; 
  flex-direction:column; 
  min-height:0; 
  width:100%; 
  max-width:560px; 
  margin:0 auto; 
  padding:0 16px;
  box-sizing:border-box;
}
/* デスクトップでのパディング調整 */
@media (min-width:600px){
  .wizard-inner { 
    padding:0 20px; 
  }
}
/* 横向き (landscape) で高さが低い場合は中央揃え & 余白微調整 */
@media (orientation:landscape){
  .wizard-wrap { align-items:center; justify-content:center; }
  .wizard-inner { flex:0 0 auto; max-height:100%; }
}
/* 各画面ルートに付与（縦中央 or フレックス伸長） */
.wizard-screen { flex:1 1 auto; display:flex; flex-direction:column; min-height:0; }
/* スクロールが必要な領域にのみ付与 */
.wizard-scroll { flex:1 1 auto; overflow:auto; -webkit-overflow-scrolling:touch; overscroll-behavior: contain; }
/* モバイルでの適切な表示 - スクロール改善とセンタリング */
@media (max-width: 768px) {
  .wizard-wrap { 
    height: 100dvh; /* 動的ビューポート高さを使用、100vhにフォールバック */
    min-height: 100vh;
    padding-top: calc(env(safe-area-inset-top) + 60px); /* ヘッダー分の余白を確保 */
    overflow-y: auto; /* モバイルで縦スクロールを有効化 */
    overflow-x: hidden; /* 横スクロールは無効化 */
    display: flex;
    justify-content: center; /* 水平センタリング追加 */
  }
  
  .wizard-inner { 
    flex: 1; 
    min-height: 0; 
    overflow: visible; /* 内側のオーバーフローを表示可能に */
    width: 100%;
    max-width: 100%; /* モバイルでは全幅使用 */
    padding: 0 12px; /* より適切なモバイルパディング */
    margin: 0 auto; /* 明示的にセンタリング */
  }
  
  .wizard-screen { 
    flex: 1; 
    display: flex;
    flex-direction: column;
    min-height: 0;
    padding-bottom: calc(env(safe-area-inset-bottom) + 80px); /* フッター分の余白を十分確保 */
    overflow: visible; /* コンテンツを表示可能に */
    margin: 0 auto; /* 画面コンテンツもセンタリング */
    width: 100%;
    max-width: 100%;
  }
  
  .wizard-scroll {
    overflow-y: auto; /* 縦スクロール有効 */
    overflow-x: hidden; /* 横スクロール無効 */
    -webkit-overflow-scrolling: touch; /* iOSでスムーススクロール */
    overscroll-behavior: contain;
    flex: 1;
    width: 100%;
    max-width: 100vw; /* ビューポート幅を超えないよう制限 */
  }
}
</style>