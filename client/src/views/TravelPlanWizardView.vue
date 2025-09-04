<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import InputScreen from '@/components/InputScreen.vue'
import LoadingScreen from '@/components/LoadingScreen.vue'
import SuggestionScreen from '@/components/SuggestionScreen.vue'
import DetailScreen from '@/components/DetailScreen.vue'

const currentView = ref('input') // 'input' | 'loading' | 'suggestions' | 'detail'
const travelPlans = ref([
  { id: 1, title: 'のんびり温泉癒し旅', tags: '#温泉 #リラックス #自然' },
  { id: 2, title: '歴史と文化を巡る旅', tags: '#歴史 #寺社仏閣 #文化体験' },
  { id: 3, title: 'アクティブアドベンチャー旅', tags: '#アクティビティ #自然 #挑戦' },
])
const selectedPlan = ref(null)

function handleCreatePlan() {
  currentView.value = 'loading'
  setTimeout(() => { currentView.value = 'suggestions' }, 3000)
}
function handleSelectPlan(p) { selectedPlan.value = p; currentView.value = 'detail' }
function handleGoBack() { currentView.value = 'suggestions' }

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

const wrapStyle = computed(() => ({
  '--vvh': viewportHeight.value ? viewportHeight.value + 'px' : undefined,
  height: 'var(--vvh)',
  maxHeight: 'var(--vvh)'
}))
</script>

<template>
  <!-- フル幅フル高表示用のラッパ -->
  <div ref="wrapEl" class="wizard-wrap bg-gradient-to-b from-white to-slate-50 text-slate-900" data-route="travel-wizard" :style="wrapStyle">
    <InputScreen v-if="currentView==='input'" @create-plan="handleCreatePlan" />
    <LoadingScreen v-else-if="currentView==='loading'" />
    <SuggestionScreen v-else-if="currentView==='suggestions'" :plans="travelPlans" @select-plan="handleSelectPlan" />
    <DetailScreen v-else-if="currentView==='detail'" :plan="selectedPlan" @go-back="handleGoBack" />
  </div>
</template>

<style scoped>
/* App.vue 側で .content の padding を外した状態で内部を全域化 */
.wizard-wrap { height:var(--vvh,100dvh); max-height:var(--vvh,100dvh); min-height:100vh; width:100%; display:flex; flex-direction:column; overflow:hidden; }
/* 各画面ルートに付与（縦中央 or フレックス伸長） */
.wizard-screen { flex:1 1 auto; display:flex; flex-direction:column; min-height:0; }
/* スクロールが必要な領域にのみ付与 */
.wizard-scroll { flex:1 1 auto; overflow:auto; -webkit-overflow-scrolling:touch; overscroll-behavior: contain; }
/* 余白縮小（小画面） */
@media (max-width:600px){
  .wizard-screen { padding-bottom: env(safe-area-inset-bottom); }
}
</style>