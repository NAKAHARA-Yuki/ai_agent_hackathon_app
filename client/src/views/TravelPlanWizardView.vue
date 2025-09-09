<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { agentChat } from '@/services/apiClient'
import InputScreen from '@/components/InputScreen.vue'
import LoadingScreen from '@/components/LoadingScreen.vue'
import SuggestionScreen from '@/components/SuggestionScreen.vue'
import DetailScreen from '@/components/DetailScreen.vue'
import { useAuthStore } from '@/stores/authStore'
import { createPlan } from '@/services/apiClient'

const currentView = ref('input') // 'input' | 'loading' | 'suggestions' | 'detail'
const travelPlans = ref([])
const selectedPlan = ref(null)
const saving = ref(false)
const auth = useAuthStore()

async function handleCreatePlan(keyword) {
  if (!keyword || currentView.value !== 'input') return
  currentView.value = 'loading'
  try {
    // 簡易セッション: wizard 用にランダム ID
    const sessionId = crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`
    const resp = await agentChat({ message: keyword, user_id: auth.user?.id || 'u_local', session_id: sessionId, authHeader: auth.authHeader() })
    // suggestions -> travelPlans
    let mapped = []
    if (Array.isArray(resp.plans) && resp.plans.length) {
      mapped = resp.plans.slice(0,3).map((p,i)=>({
        id: i+1,
        title: p.title || `プラン ${i+1}`,
        tags: (p.tags||[]).map(t=>`#${t}`).join(' '),
        brief: p.brief || '',
        itinerary: p.itinerary || [],
        places: p.places || [],
        route_info: p.route_info || null,
        text: p.text || '',
        __raw: p,
        __full: resp
      }))
    } else {
      const sugg = Array.isArray(resp.suggestions) ? resp.suggestions : []
      mapped = sugg.slice(0,3).map((s,i)=>({
        id: i+1,
        title: s.title || `プラン ${i+1}`,
        tags: (s.tags||[]).map(t=>`#${t}`).join(' '),
        brief: s.brief || '',
        itinerary: (resp.itinerary||[]),
        __raw: s,
        __full: resp
      }))
      if (!mapped.length) {
        mapped.push({ id:1, title: resp.summary || '旅行プラン', tags: '', brief: '', itinerary: resp.itinerary||[], __full: resp })
      }
    }
    travelPlans.value = mapped
    currentView.value = 'suggestions'
  } catch(e){
    console.error('wizard agent error', e)
    // フォールバック静的案
    travelPlans.value = [
      { id:1, title:'サンプル温泉旅', tags:'#温泉 #リラックス', brief:'フォールバック案', itinerary:[] }
    ]
    currentView.value = 'suggestions'
  }
}
function handleSelectPlan(p) { selectedPlan.value = p; currentView.value = 'detail' }
function handleGoBack() { currentView.value = 'suggestions' }
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
  
  handleCreatePlan(keyword)
}
async function handleConfirm(plan){
  if(saving.value) return
  try {
    saving.value = true
    const full = plan.__full || {}
    const payload = { 
      title: plan.title, 
      text: full.text || plan.tags || '', 
      places: full.places || [], 
      route_info: full.route_info || null, 
      status: 'confirmed',
      summary: full.summary || null,
      suggestions: full.suggestions || [],
      itinerary: full.itinerary || []
    }
    await createPlan(payload, auth.authHeader())
    // 保存後ホーム（main）へ遷移 or 予定へ
    window.location.assign('/schedule')
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
      <SuggestionScreen v-else-if="currentView==='suggestions'" :plans="travelPlans" @select-plan="handleSelectPlan" @regenerate="handleRegenerate" />
  <DetailScreen v-else-if="currentView==='detail'" :plan="selectedPlan" @go-back="handleGoBack" @confirm="handleConfirm" />
    </div>
  </div>
</template>

<style scoped>
/* ルートラッパ: 親 flex 領域にフィット / 余白除去 */
.wizard-wrap { flex:1 1 auto; width:100%; height:100%; display:flex; flex-direction:column; overflow:hidden; position:relative; margin:0; }
/* 中央固定幅コンテナ (幅 >600px でセンター) */
.wizard-inner { flex:1 1 auto; display:flex; flex-direction:column; min-height:0; width:100%; margin:0 auto; }
@media (min-width:600px){
  .wizard-inner { max-width:560px; width:100%; }
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
/* 余白縮小（小画面） */
@media (max-width:600px){
  .wizard-screen { padding-bottom: env(safe-area-inset-bottom); }
}
</style>