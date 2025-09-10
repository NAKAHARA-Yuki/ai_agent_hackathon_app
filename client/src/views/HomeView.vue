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
  <main class="home">
    <div class="card">
      <h1>あなたの旅行スタイル診断</h1>
      <p>いくつかの簡単な質問に答えて、あなたにぴったりの旅行タイプを見つけましょう。</p>
      <button @click="startQuiz">診断を始める</button>
    </div>
  </main>
</template>

<style scoped>
.home { display:grid; place-items:center; height:100%; padding:16px; }
.card {
  text-align: center;
}
p {
  margin: 20px 0;
  color: #555;
}

/* モバイルでの全画面対応 */
@media (max-width: 768px) {
  .home { 
    padding: 0; 
    place-items: stretch;
  }
}
</style>
