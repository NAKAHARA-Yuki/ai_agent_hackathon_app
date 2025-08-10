<script setup>
import { onMounted } from 'vue'
import { useQuizStore } from '@/stores/quizStore'
import { useRouter } from 'vue-router'

const store = useQuizStore()
const router = useRouter()

onMounted(() => {
  if (Object.keys(store.userAnswers).length > 0) {
    store.analyzeFreeTextAnswers()
  }
})

function restartQuiz() {
  store.resetQuiz()
  router.push('/')
}
</script>

<template>
  <div class="card result-card">
    <h1>診断結果</h1>
    <div v-if="store.isAnalyzing">
      <p>自由記述の内容をAIが分析中です...</p>
      <div class="spinner"></div>
    </div>
    <div v-else-if="store.finalResult">
        <h2>あなたの旅行タイプは... <strong>{{ store.finalResult.title }}</strong> です！</h2>
        <p>{{ store.finalResult.description }}</p>
    </div>
     <div v-else>
      <p>結果を計算中です...</p>
    </div>
    <button @click="restartQuiz" :disabled="store.isAnalyzing">もう一度診断する</button>
  </div>
</template>

<style scoped>
.result-card {
  text-align: center;
}
h2 {
  margin: 20px 0;
  color: #333;
}
h2 strong {
  color: #007bff;
}
p {
  font-size: 1.1rem;
  line-height: 1.6;
  color: #555;
  margin-bottom: 30px;
}
.spinner {
  border: 4px solid rgba(0, 0, 0, 0.1);
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border-left-color: #007bff;
  margin: 20px auto;
  animation: spin 1s ease infinite;
}
@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}
</style>
