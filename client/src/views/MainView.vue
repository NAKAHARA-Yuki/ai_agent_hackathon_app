<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { useQuizStore } from '@/stores/quizStore'
import { useActivePlanStore } from '@/stores/activePlanStore'
import VIcon from '@/components/v-icon.vue'

const router = useRouter()
const auth = useAuthStore()
const quiz = useQuizStore()
const activePlanStore = useActivePlanStore()
const persona = ref(null)
const loading = ref(true)
const error = ref('')
const hasResult = computed(() => !!quiz.finalResult)
const recentPlans = ref([])
const plansLoading = ref(true)

// Helper function to validate persona data
function isValidPersona(data) {
  return data && 
         typeof data === 'object' && 
         data.profile && 
         data.profile.title
}

async function loadLatestPersona() {
  try {
    const resp = await fetch('/api/persona/latest', { headers: { ...auth.authHeader() } })
    if (resp.ok) {
      const data = await resp.json()
      if (isValidPersona(data)) {
        persona.value = data
      } else {
        console.warn('Invalid persona data received:', data)
        persona.value = null
      }
    } else {
      console.log('No persona data found (HTTP', resp.status + ')')
      persona.value = null
    }
  } catch (e) {
    console.error('Failed to load persona:', e)
    error.value = e?.message || '読み込みに失敗しました'
    persona.value = null
  } finally {
    loading.value = false
  }
}

async function loadRecentPlans() {
  try {
    const resp = await fetch('/api/plans', { headers: { ...auth.authHeader() } })
    if (resp.ok) {
      const data = await resp.json()
      // Get the most recent 3 plans
      recentPlans.value = (data.items || []).slice(0, 3).map(plan => ({
        id: plan.id,
        title: plan.title,
        summary: plan.summary || plan.brief || '',
        date: (plan.created_at && plan.created_at.seconds ? 
          new Date(plan.created_at.seconds * 1000) : new Date()).toLocaleDateString('ja-JP'),
        status: plan.status || 'confirmed'
      }))
    }
  } catch (e) {
    console.error('Failed to load recent plans:', e)
  } finally {
    plansLoading.value = false
  }
}

onMounted(() => {
  loadLatestPersona()
  loadRecentPlans()
  // Fetch active plan for travel day mode
  activePlanStore.fetchActivePlan()
})

function goResults() {
  router.push({ name: 'results' })
}

function restart() {
  router.push({ name: 'home' })
}

function openTravelDayChat() {
  if (activePlanStore.activePlanId) {
    router.push({ name: 'travel-day-chat', params: { id: activePlanStore.activePlanId } })
  }
}

</script>

<template>
  <div class="page-without-local-footer">
    <main class="main">
      <section class="panel">
  <h1>メインページ</h1>
      <p class="lead">あなたの診断に基づき、パーソナライズされた旅の提案を続けられます。</p>

      <!-- Active Plan Quick Access (Travel Day Mode) -->
      <div v-if="activePlanStore.isActive" class="active-plan-banner">
        <div class="banner-content">
          <div class="banner-info">
            <div class="banner-title">{{ activePlanStore.activePlanTitle }}</div>
            <div class="banner-subtitle">旅行当日モード中</div>
          </div>
          <button @click="openTravelDayChat" class="chat-btn" aria-label="旅行当日チャット">
            <VIcon name="chat" :size="20" aria-label="チャット" />
            チャット
          </button>
        </div>
      </div>

      <div v-if="loading">読み込み中...</div>
      <div v-else-if="error" class="error">
        <p>エラーが発生しました: {{ error }}</p>
        <button @click="loadLatestPersona" class="retry-btn">再試行</button>
      </div>
      <div v-else>
        <div v-if="persona?.profile?.title">
          <h3>現在のタイプ: {{ persona.profile.title }}</h3>
          <p>{{ persona.profile.description || '詳細情報は現在利用できません。' }}</p>
          <div v-if="persona.profile?.traitScores && Object.keys(persona.profile.traitScores).length > 0" class="trait-summary">
            <h4>📊 あなたの特性</h4>
            <div class="trait-compact-list">
              <div v-for="(score, trait) in persona.profile.traitScores" :key="trait" class="trait-compact-item">
                <span class="trait-compact-name">{{ trait }}</span>
                <div class="trait-compact-bar">
                  <div class="trait-compact-fill" :style="{ width: (score / 4) * 100 + '%' }"></div>
                  <span class="trait-compact-score">{{ score }}</span>
                </div>
              </div>
            </div>
            <small class="muted">診断結果に基づいてパーソナライズされています</small>
          </div>
        </div>
        <div v-else class="muted">まだペルソナがありません。診断を実施してください。</div>

        <div class="actions">
          <button class="primary" @click="router.push({ name: 'travel-wizard' })">旅行計画の作成</button>
        </div>

        <!-- Recent Travel Plans Section -->
        <div class="recent-plans" v-if="!plansLoading">
          <h3>最近の旅行プラン</h3>
          <div v-if="recentPlans.length > 0" class="plans-list">
            <div 
              v-for="plan in recentPlans" 
              :key="plan.id" 
              class="plan-item"
              @click="router.push({ name: 'plan-detail', params: { id: plan.id } })"
              tabindex="0"
              @keydown.enter.prevent="router.push({ name: 'plan-detail', params: { id: plan.id } })"
            >
              <div class="plan-main">
                <div class="plan-title">{{ plan.title }}</div>
                <div v-if="plan.summary" class="plan-summary">{{ plan.summary }}</div>
                <div class="plan-meta">
                  <span class="plan-date">{{ plan.date }}</span>
                  <span class="plan-status" :class="plan.status">{{ plan.status === 'confirmed' ? '確定' : '下書き' }}</span>
                </div>
              </div>
            </div>
          </div>
          <p v-else class="no-plans">まだ保存されたプランがありません。</p>
        </div>
        <div v-else class="recent-plans loading">
          <h3>最近の旅行プラン</h3>
          <p>読み込み中...</p>
        </div>
      </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.page-without-local-footer { display:flex; flex-direction:column; height:100%; width:100%; overflow:hidden; }
.main { flex:1 1 auto; display:grid; place-items:center; padding:32px 16px 24px; width:100%; overflow:auto; }
.panel { width:min(920px,100%); background:white; padding:24px 20px; border-radius:14px; box-shadow:0 10px 24px rgba(0,0,0,0.06); border:1px solid #eef2f7; }
.lead { color:#5a6b86; margin: 0 0 16px; }
.muted { color:#6b7280; }

/* モバイルでの適切な表示 */
@media (max-width: 768px) {
  .main { 
    padding: 16px; 
  }
  .panel { 
    width: 100%; 
    border-radius: var(--radius-lg); 
    box-shadow: var(--shadow-md); 
    border: 1px solid var(--color-border);
    padding: 16px;
    box-sizing: border-box;
  }
}
.error { 
  color: #dc2626; 
  padding: 16px; 
  background: #fef2f2; 
  border-radius: 8px; 
  border: 1px solid #fecaca; 
  margin-bottom: 16px; 
}
.retry-btn { 
  background: #dc2626; 
  color: white; 
  border: none; 
  border-radius: 6px; 
  padding: 8px 12px; 
  margin-top: 8px; 
  cursor: pointer; 
}
.retry-btn:hover { 
  background: #b91c1c; 
}
.trait-summary {
  margin-top: 16px;
}

.trait-summary h4 {
  margin: 0 0 12px 0;
  font-size: 16px;
  font-weight: 600;
  color: #374151;
}

.trait-compact-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}

.trait-compact-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 6px;
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.trait-compact-name {
  font-size: 12px;
  font-weight: 500;
  color: #374151;
  min-width: 80px;
  flex-shrink: 0;
}

.trait-compact-bar {
  flex: 1;
  position: relative;
  background: #e0e7ff;
  height: 16px;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  align-items: center;
}

.trait-compact-fill {
  background: linear-gradient(90deg, #3b82f6, #1d4ed8);
  height: 100%;
  border-radius: 8px;
  transition: width 0.5s ease;
  min-width: 12px;
}

.trait-compact-score {
  position: absolute;
  right: 4px;
  font-size: 10px;
  font-weight: 600;
  color: #1f2937;
  background: rgba(255, 255, 255, 0.9);
  padding: 1px 3px;
  border-radius: 3px;
  min-width: 12px;
  text-align: center;
}

.trait-summary small {
  font-size: 12px;
  color: #9ca3af;
}
.actions { margin-top: 16px; display:flex; gap: 12px; }
.primary { background: var(--color-primary); color:#fff; border:none; border-radius:10px; padding:10px 16px; }

/* Recent Plans Section */
.recent-plans { 
  margin-top: 24px; 
  padding-top: 20px; 
  border-top: 1px solid #e5e7eb; 
}

.recent-plans h3 { 
  margin: 0 0 12px 0; 
  font-size: 16px; 
  font-weight: 600; 
  color: #374151; 
}

.plans-list { 
  display: flex; 
  flex-direction: column; 
  gap: 8px; 
}

.plan-item { 
  background: #f9fafb; 
  border: 1px solid #e5e7eb; 
  border-radius: 8px; 
  padding: 12px; 
  cursor: pointer; 
  transition: all 0.2s; 
}

.plan-item:hover { 
  background: #f3f4f6; 
  border-color: #d1d5db; 
  transform: translateY(-1px); 
  box-shadow: 0 2px 4px rgba(0,0,0,0.05); 
}

.plan-item:focus-visible { 
  outline: 2px solid var(--color-primary); 
  outline-offset: 2px; 
}

.plan-title { 
  font-size: 14px; 
  font-weight: 600; 
  color: #1f2937; 
  margin-bottom: 4px; 
}

.plan-summary { 
  font-size: 12px; 
  color: #6b7280; 
  line-height: 1.4; 
  margin-bottom: 6px; 
  display: -webkit-box; 
  -webkit-line-clamp: 2; 
  -webkit-box-orient: vertical; 
  overflow: hidden; 
}

.plan-meta { 
  display: flex; 
  align-items: center; 
  justify-content: space-between; 
}

.plan-date { 
  font-size: 11px; 
  color: #9ca3af; 
}

.plan-status { 
  font-size: 10px; 
  padding: 2px 6px; 
  border-radius: 12px; 
  font-weight: 600; 
  letter-spacing: 0.5px; 
  background: #e5e7eb; 
  color: #6b7280; 
}

.plan-status.confirmed { 
  background: #dbeafe; 
  color: #1d4ed8; 
}

.plan-status.draft { 
  background: #fef3c7; 
  color: #b45309; 
}

.no-plans { 
  font-size: 12px; 
  color: #9ca3af; 
  text-align: center; 
  padding: 16px 0; 
}

.recent-plans.loading { 
  color: #9ca3af; 
}

/* Active Plan Banner */
.active-plan-banner {
  background: linear-gradient(135deg, #10b981, #059669);
  color: white;
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 4px 16px rgba(16, 185, 129, 0.3);
  margin-bottom: 16px;
  box-sizing: border-box; /* avoid overflow on desktop */
}

.banner-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap; /* allow wrapping to avoid overlap on desktop */
  gap: 12px; /* spacing between title and button when wrapped */
}

.banner-info {
  flex: 1 1 auto;
  min-width: 0; /* allow text to shrink in flex container */
  overflow: hidden; /* clamp overflowing title */
}

.banner-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap; /* keep one line on desktop */
}

.banner-subtitle {
  font-size: 12px;
  opacity: 0.9;
}

.chat-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border: none;
  border-radius: 12px;
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0; /* prevent shrinking and overlap */
  margin-left: auto; /* keep button on the far right when space allows */
}

.chat-btn:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: translateY(-1px);
}

.chat-btn svg {
  width: 16px;
  height: 16px;
}

@media (max-width: 600px){ 
  .banner-content {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  
  .chat-btn {
    align-self: stretch;
    justify-content: center;
    padding: 10px 18px;
    font-size: 15px;
    min-height: 44px; /* タッチフレンドリーなサイズ */
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
