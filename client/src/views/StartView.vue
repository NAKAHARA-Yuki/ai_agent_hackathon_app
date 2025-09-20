<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useQuizStore } from '@/stores/quizStore'
import { useAuthStore } from '@/stores/authStore'

const router = useRouter()
const quizStore = useQuizStore()
const auth = useAuthStore()
const step = ref(0)
const loading = ref(false)

async function startQuiz() {
  if (loading.value) return
  loading.value = true
  await quizStore.fetchQuestions()
  if (quizStore.totalQuestions > 0) {
    quizStore.resetQuiz()
    router.push({ name: 'question', params: { questionNumber: 1 } })
  } else {
    alert('旅行スタイル診断の読み込みに失敗しました。')
  }
  loading.value = false
}

function nextStep() {
  if (step.value < 2) step.value += 1
}

function prevStep() {
  if (step.value > 0) step.value -= 1
}

onMounted(async () => {
  // このビューでは縦スクロールを無効化
  const prevHtmlOverflowY = document.documentElement.style.overflowY
  const prevBodyOverflowY = document.body.style.overflowY
  document.documentElement.style.overflowY = 'hidden'
  document.body.style.overflowY = 'hidden'
  // フッターを非表示
  document.body.classList.add('hide-footer')

  onUnmounted(() => {
    document.documentElement.style.overflowY = prevHtmlOverflowY
    document.body.style.overflowY = prevBodyOverflowY
    document.body.classList.remove('hide-footer')
  })

  // すでに診断済みならメインへ
  if (auth.isAuthenticated) {
    try {
      await auth.refreshMe()
      if (auth.user?.diagnosis_completed) {
        router.replace({ name: 'main' })
        return
      }
    } catch {}
  }
})
</script>

<template>
  <main class="start">
    <section class="hero">
      <h1>あなたの旅行スタイル診断</h1>
      <p class="sub">数分でわかる、ぴったりの旅タイプ。AIが国内旅行プランも提案します。</p>

      <div class="stepper" aria-label="紹介ステップ">
        <span :class="['dot', { active: step===0 }]"></span>
        <span :class="['dot', { active: step===1 }]"></span>
        <span :class="['dot', { active: step===2 }]"></span>
      </div>

      <div class="slides">
        <transition name="fade" mode="out-in">
          <div :key="step">
            <template v-if="step===0">
              <h3>1. かんたんに答えるだけ</h3>
              <p>直感的な質問に選択で回答。迷ったら自由記述もOKです。</p>
            </template>
            <template v-else-if="step===1">
              <h3>2. タイプを可視化</h3>
              <p>10の特性をスコア化して、あなたの傾向をレーダーチャートで表示。</p>
            </template>
            <template v-else>
              <h3>3. AIが国内旅行プランを提案</h3>
              <p>診断結果に基づいて、日本国内に限定した旅程を自動生成します。</p>
            </template>
          </div>
        </transition>
      </div>

      <div class="actions">
        <button class="ghost" v-if="step>0" @click="prevStep">戻る</button>
        <button class="primary" v-if="step<2" @click="nextStep">次へ</button>
        <button class="primary" v-else @click="startQuiz" :disabled="loading" :aria-busy="loading">
          {{ loading ? '読み込み中…' : '診断を開始する' }}
        </button>
      </div>
    </section>
  </main>
</template>

<style scoped>
/* グローバルの余白/高さのみ調整（スクロール制御はクラスで切替） */
:global(html, body, #app) { height: 100%; margin: 0; }
/* StartView表示中（body.hide-footer）だけスクロール抑制 */
:global(body.hide-footer) { overflow: hidden; overscroll-behavior: none; }
/* StartView表示中のみ（body.hide-footer）フッターを消す（実体は .footer-nav） */
:global(body.hide-footer .footer-nav) { display: none !important; }
.start {
  display: grid;
  place-items: center;
  padding: 16px;
  /* viewport基準で縦センタリングが効くようにする */
  min-height: 100dvh; /* Safari等では 100vh の代わりに dvh が有効 */
  /* フォールバック */
  /* 固定配置で確実に全画面＆スクロール抑止 */
  position: fixed;
  inset: 0;
  height: 100svh; /* 安定したビューポート高さ */
  place-content: center;
  justify-items: center; /* 横方向のセンタリングを明示 */
  width: 100%;
  box-sizing: border-box; /* paddingで縦スクロールが出ないようにする */
  overflow: hidden; /* 内側のはみ出しでスクロールが発生しないように */
}

.hero {
  text-align: center;
  background: white;
  padding: 40px 24px;
  border-radius: 16px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.08);
  width: min(960px, 100%);
  margin: 0 auto; /* 念のため水平方向の中央寄せを明示 */
  margin-inline: auto; /* 双方向対応の水平センタリング */
}

.hero h1 {
  font-size: 28px;
  margin: 0 0 12px;
}

.hero .sub {
  color: #5a6b86;
  margin: 0 auto 24px;
}

.actions { display:flex; justify-content:center; gap: 12px; }

button.primary {
  background: var(--color-primary);
  color: #fff;
  border: none;
  padding: 12px 20px;
  border-radius: 10px;
  font-size: 16px;
  cursor: pointer;
  transition: transform .06s ease, box-shadow .2s ease;
  box-shadow: 0 6px 16px rgba(45,126,247,0.35);
}

button.primary:hover { transform: translateY(-1px); }
button.primary:active { transform: translateY(0); box-shadow: 0 3px 10px rgba(45,126,247,0.35); }

button.ghost {
  background: transparent;
  color: #1f2937;
  border: 1px solid rgba(0,0,0,0.1);
  padding: 12px 16px;
  border-radius: 10px;
  cursor: pointer;
}

.stepper { display:flex; justify-content:center; gap:8px; margin: 14px 0 8px; }
.dot { width:8px; height:8px; border-radius:50%; background:#c7d2fe; }
.dot.active { background:#4f46e5; }

/* シンプルなフェード遷移 */
.fade-enter-active,
.fade-leave-active { transition: opacity .2s ease; }
.fade-enter-from,
.fade-leave-to { opacity: 0; }

/* スライド領域も横方向中央に */
.slides { margin-inline: auto; }

@media (max-width: 800px) {
  .hero { padding: 32px 18px; }
}
</style>
