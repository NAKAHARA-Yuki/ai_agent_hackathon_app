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
  <div class="card">
    <h1>あなたの旅行スタイル診断</h1>
    <p>いくつかの簡単な質問に答えて、あなたにぴったりの旅行タイプを見つけましょう。</p>
    <button @click="startQuiz">診断を始める</button>
  </div>
</template>

<style scoped>
.card {
  text-align: center;
}
p {
  margin: 20px 0;
  color: #555;
}
</style>
