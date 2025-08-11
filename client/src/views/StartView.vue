<script setup>
import { useRouter } from 'vue-router'
import { useQuizStore } from '@/stores/quizStore'

const router = useRouter()
const quizStore = useQuizStore()

async function startQuiz() {
  await quizStore.fetchQuestions()
  if (quizStore.totalQuestions > 0) {
    quizStore.resetQuiz()
    router.push({ name: 'question', params: { questionNumber: 1 } })
  } else {
    alert('クイズの読み込みに失敗しました。')
  }
}
</script>

<template>
  <main class="start">
    <section class="hero">
      <h1>あなたの旅行スタイル診断</h1>
      <p class="sub">数分でわかる、ぴったりの旅タイプ。AIが国内旅行プランも提案します。</p>

      <div class="actions">
        <button class="primary" @click="startQuiz">診断を始める</button>
      </div>
    </section>

    <section class="features">
      <div class="feature">
        <h3>かんたん回答</h3>
        <p>直感的な質問に答えるだけ。迷ったら自由記述もOK。</p>
      </div>
      <div class="feature">
        <h3>タイプ診断</h3>
        <p>10の特性をスコア化して、あなたの傾向を可視化。</p>
      </div>
      <div class="feature">
        <h3>AIプラン</h3>
        <p>日本国内に限定したおすすめ旅程をAIが自動生成。</p>
      </div>
    </section>
  </main>
  
</template>

<style scoped>
.start {
  display: grid;
  gap: 40px;
  padding: 32px 20px;
  max-width: 960px;
  width: 100%;
}

.hero {
  text-align: center;
  background: white;
  padding: 40px 24px;
  border-radius: 16px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.08);
}

.hero h1 {
  font-size: 28px;
  margin: 0 0 12px;
}

.hero .sub {
  color: #5a6b86;
  margin: 0 auto 24px;
}

.actions {
  display: flex;
  justify-content: center;
}

button.primary {
  background: #2d7ef7;
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

.features {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.feature {
  background: rgba(255,255,255,0.85);
  backdrop-filter: blur(6px);
  padding: 20px;
  border-radius: 14px;
  border: 1px solid rgba(0,0,0,0.05);
}

.feature h3 {
  margin: 0 0 8px;
  font-size: 18px;
}
.feature p { margin: 0; color: #5a6b86; }

@media (max-width: 800px) {
  .features { grid-template-columns: 1fr; }
  .hero { padding: 32px 18px; }
}
</style>
