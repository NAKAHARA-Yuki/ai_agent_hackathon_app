<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import InputScreen from '@/components/InputScreen.vue'
import LoadingScreen from '@/components/LoadingScreen.vue'
import SuggestionScreen from '@/components/SuggestionScreen.vue'
import DetailScreen from '@/components/DetailScreen.vue'
import { useAuthStore } from '@/stores/authStore'
import { createPlan } from '@/services/apiClient'

const currentView = ref('input') // 'input' | 'loading' | 'suggestions' | 'detail'
const travelPlans = ref([
  { id: 1, title: 'のんびり温泉癒し旅', tags: '#温泉 #リラックス #自然' },
  { id: 2, title: '歴史と文化を巡る旅', tags: '#歴史 #寺社仏閣 #文化体験' },
  { id: 3, title: 'アクティブアドベンチャー旅', tags: '#アクティビティ #自然 #挑戦' },
])
const selectedPlan = ref(null)
const saving = ref(false)
const auth = useAuthStore()

function handleCreatePlan() {
  currentView.value = 'loading'
  setTimeout(() => { currentView.value = 'suggestions' }, 3000)
}
function handleSelectPlan(p) { selectedPlan.value = p; currentView.value = 'detail' }
function handleGoBack() { currentView.value = 'suggestions' }
async function handleConfirm(plan){
  if(saving.value) return
  try {
    saving.value = true
    const payload = { title: plan.title, text: plan.tags || '', places: [], route_info: null, status: 'confirmed' }
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
      <SuggestionScreen v-else-if="currentView==='suggestions'" :plans="travelPlans" @select-plan="handleSelectPlan" />
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