<script setup>
import { onMounted, ref, computed, watch } from 'vue'
import { useQuizStore } from '@/stores/quizStore'
import { useAuthStore } from '@/stores/authStore'
import { useRouter } from 'vue-router'
import ResultChart from '@/components/ResultChart.vue'
import BackButton from '@/components/BackButton.vue'

const store = useQuizStore()
const auth = useAuthStore()
const router = useRouter()
const showScoreDetails = ref(false)
const personaData = ref(null)
const loading = ref(false)

// Load persona data from API if quiz store doesn't have results
async function loadPersonaData() {
  if (personaData.value) return // Already loaded
  try {
    loading.value = true
    const resp = await fetch('/api/persona/latest', { headers: { ...auth.authHeader() } })
    if (resp.ok) {
      const data = await resp.json()
      if (data?.profile) {
        personaData.value = data
      }
    }
  } catch (e) {
    console.error('Failed to load persona data:', e)
  } finally {
    loading.value = false
  }
}

// Combined result data - use quiz store if available, otherwise use persona API data
const displayResult = computed(() => {
  // If quiz store has fresh results and average is valid, use those
  if (store.finalResult && store.finalResult.scoreDetails && !isNaN(parseFloat(store.finalResult.scoreDetails.average))) {
    return store.finalResult
  }
  
  // Otherwise, construct from persona data
  if (personaData.value?.profile) {
    const profile = personaData.value.profile
    const traitScores = profile.traitScores || {}
    
    // Calculate average score
    const scores = Object.values(traitScores).filter(score => !isNaN(score))
    const average = scores.length > 0 ? scores.reduce((sum, score) => sum + score, 0) / scores.length : 0
    
    return {
      title: profile.title || '診断結果',
      description: profile.description || '',
      plans: [], // No plans from persona data
      scoreDetails: {
        average: average.toFixed(2),
        traitScores: traitScores,
        answers: [] // No individual answers from persona data
      }
    }
  }
  
  return null
})

const traitsOrder = computed(() => {
  // If we have persona data, use the trait keys from there
  if (personaData.value?.profile?.traitScores) {
    return Object.keys(personaData.value.profile.traitScores)
  }
  // Otherwise use questions data (for fresh quiz results)
  const order = []
  const seen = new Set()
  for (const q of store.questions || []) {
    if (q?.trait && !seen.has(q.trait)) {
      seen.add(q.trait)
      order.push(q.trait)
    }
  }
  return order
})

const traitDescriptions = computed(() => {
  // For persona data, provide fallback descriptions since we don't have questions
  if (personaData.value?.profile?.traitScores) {
    const fallbackDescriptions = {
      '新規性追求': '未知や型にはまらない体験をどれだけ求めるか（冒険型〜安定志向の連続）。',
      '旅程密度': '1日の予定をどれだけ詰め込むか（行動満載〜余白重視）。',
      '予算哲学': '価格・コスパ重視か、体験の質を優先するか。',
      '社会的志向性': '現地の人／他の旅行者との交流をどれだけ望むか。',
      '主な興味関心': '旅行の中心テーマ（例：グルメ、自然、文化・歴史、リラクゼーション）。',
      '計画志向性': '事前に緻密に計画するか、現地で柔軟に決めるか。',
      '快適性水準': '宿・移動における快適さ・アメニティの重視度。',
      '活動レベル': '旅行中の身体的アクティビティの強度。',
      '安全性の閾値': '治安・医療など安全面をどの程度重視するか。',
      'デジタル統合度': '計画から共有までテクノロジーをどれだけ活用するか。'
    }
    const map = {}
    Object.keys(personaData.value.profile.traitScores).forEach(trait => {
      map[trait] = fallbackDescriptions[trait] || `${trait}に関する特性スコア`
    })
    return map
  }
  // Otherwise use questions data (for fresh quiz results)
  if (!store.questions?.length) return {}
  const map = {}
  for (const q of store.questions) {
    if (q?.trait && !(q.trait in map)) {
      map[q.trait] = q.trait_description
    }
  }
  return map
})

onMounted(async () => {
  // Load persona data if quiz store doesn't have valid results (missing data or NaN average)
  if (!store.finalResult || !store.finalResult.scoreDetails || isNaN(parseFloat(store.finalResult.scoreDetails.average))) {
    await loadPersonaData()
  }
})

function restartQuiz() {
  store.resetQuiz()
  router.push('/')
}

function toggleScoreDetails() {
  showScoreDetails.value = !showScoreDetails.value
}

function goMain() {
  router.push({ name: 'main' })
}
</script>

<template>
  <main class="result-view">
  <div class="card result-card">
  <BackButton />
    <div v-if="loading">
      <h1>読み込み中...</h1>
      <p>診断結果を読み込んでいます。</p>
      <div class="spinner"></div>
    </div>
    <div v-else-if="store.isAnalyzing || store.isGeneratingPlans || store.isProcessing">
      <h1>診断中...</h1>
      <p>AIがあなたの回答全体を解析し、旅行タイプとおすすめプランを生成しています。少々お待ちください。</p>
      <div class="spinner"></div>
    </div>
    <div v-else-if="displayResult && displayResult.scoreDetails">
      <div class="result-section result-summary">
        <h2>🎉 診断結果 🎉</h2>
        <h3>あなたの旅行タイプは... <strong>{{ displayResult.title }}</strong> です！</h3>
        <p>{{ displayResult.description }}</p>
        <p><strong>総合平均スコア: {{ displayResult.scoreDetails.average }}</strong></p>
      </div>

            <div class="result-section chart-section">
         <ResultChart
           v-if="displayResult?.scoreDetails?.traitScores"
           :traitScores="displayResult.scoreDetails.traitScores"
           :traitDescriptions="traitDescriptions"
           :traitsOrder="traitsOrder"
         />
      </div>

      <div class="result-section travel-plans" v-if="displayResult.plans && displayResult.plans.length > 0">
        <h3>✈️ おすすめの旅行プラン</h3>
        <div v-if="store.isGeneratingPlans">AIがあなた向けの国内プランを作成中です…</div>
        <ul v-else>
          <li v-for="(plan, index) in displayResult.plans" :key="index">
            <strong>{{ plan.title }}</strong>: {{ plan.description }}
          </li>
        </ul>
      </div>

      <div class="result-section score-details" v-if="displayResult.scoreDetails.answers && displayResult.scoreDetails.answers.length > 0">
        <h3 @click="toggleScoreDetails" class="collapsible-header">
          📝 回答ごとのスコア詳細
          <span class="toggle-icon">{{ showScoreDetails ? '▲' : '▼' }}</span>
        </h3>
        <transition name="fade">
          <div v-if="showScoreDetails">
            <p class="score-note">スコアは1(依存型)〜4(冒険型)で評価されます。</p>
            <div class="table-container">
              <table>
                <thead>
                  <tr>
                    <th>質問</th>
                    <th>最終スコア</th>
                    <th>AIによる解説</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(answer, index) in displayResult.scoreDetails.answers" :key="index">
                    <td>{{ answer.question }}</td>
                    <td>{{ answer.finalScore.toFixed(2) }}</td>
                    <td>{{ answer.explanation }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </transition>
      </div>
      <div class="result-actions">
        <button class="primary" @click="goMain">メインページへ進む</button>
      </div>
    </div>
    <div v-else>
      <h1>結果</h1>
      <p>診断結果が見つかりません。診断を開始してください。</p>
      <div class="result-actions">
        <button class="primary" @click="restartQuiz">診断を開始する</button>
      </div>
    </div>
      <button @click="restartQuiz" :disabled="store.isAnalyzing">もう一度診断する</button>
    </div>
  </main>
</template>

<style scoped>
.result-view { 
  display:flex; 
  flex-direction:column; 
  align-items:center; 
  min-height:100vh; 
  padding: calc(80px + env(safe-area-inset-top)) 16px calc(80px + env(safe-area-inset-bottom)); 
  overflow-y:auto; 
  width: 100%; 
  box-sizing: border-box;
}
.result-card {
  width: min(960px, 100%);
  box-sizing: border-box;
  text-align: center;
  animation: fadeIn 0.5s ease-in-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

.result-section {
  background: rgba(255, 255, 255, 0.7);
  margin-bottom: 25px;
  padding: 25px;
  border-radius: 10px;
  border: 1px solid rgba(0, 0, 0, 0.05);
  word-break: break-word;
  overflow-wrap: anywhere;
}

h2 {
  font-size: 2rem;
  color: #333;
  margin-top: 0;
}

h3 {
  font-size: 1.5rem;
  color: #1a237e;
  margin-bottom: 15px;
}

h3 strong {
  color: #ff4b2b;
  display: block;
  margin-top: 10px;
}

p {
  font-size: 1.1rem;
  line-height: 1.7;
  color: #444;
}

.travel-plans ul {
  list-style-type: none;
  padding: 0;
}

.travel-plans li {
  margin-bottom: 15px;
  line-height: 1.6;
  background: #fdfdff;
  padding: 15px;
  border-radius: 8px;
}

.travel-plans li strong {
  display: block;
  color: #333;
  margin-bottom: 5px;
}

.collapsible-header {
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  border-radius: 8px;
  transition: background-color 0.3s;
}
.collapsible-header:hover {
  background-color: rgba(0,0,0,0.05);
}

.toggle-icon {
  font-size: 1rem;
  transition: transform 0.3s;
}

.score-details .table-container { overflow-x: auto; }

.score-details table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 20px;
}

.score-details th, .score-details td {
  border: 1px solid #e0e0e0;
  padding: 12px 15px;
  text-align: center;
  vertical-align: middle;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.score-details th {
  background-color: #f5f5f5;
  font-weight: 600;
}

.score-details td:first-child,
.score-details td:last-child {
  text-align: left;
}

.score-details td:last-child {
  font-size: 0.95rem;
  line-height: 1.5;
}

.score-note {
  font-size: 0.9rem;
  color: #666;
  text-align: center;
  margin: 15px 0;
  padding: 10px;
  background: #f0f0f0;
  border-radius: 5px;
}

.spinner {
  border: 5px solid rgba(0, 0, 0, 0.1);
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border-left-color: #ff4b2b;
  margin: 30px auto;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.5s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
.result-actions { display:flex; justify-content:center; margin-top: 12px; }
button.primary { background: var(--color-primary); color:#fff; border:none; padding:10px 16px; border-radius:8px; }

/* モバイル向け微調整 */
@media (max-width: 600px) {
  h2 { font-size: 1.6rem; }
  h3 { font-size: 1.2rem; }
  .result-section { padding: 16px; }
  .travel-plans li { padding: 12px; }
  .score-details th, .score-details td { padding: 10px 12px; }
  .result-actions { padding: 0 4px; }
  button.primary { width: 100%; padding: 12px; }
}
</style>
