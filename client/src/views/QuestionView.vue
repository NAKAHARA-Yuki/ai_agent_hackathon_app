<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuizStore } from '@/stores/quizStore'
import ProgressBar from '@/components/ProgressBar.vue'

const route = useRoute()
const router = useRouter()
const store = useQuizStore()

const questionNumber = ref(0)
const selectedOption = ref(null)
const freeText = ref('')

const currentQuestion = computed(() => {
  if (store.questions && store.questions.length > 0 && questionNumber.value > 0) {
    return store.questions[questionNumber.value - 1]
  }
  return null
})

function updateQuestionState(newVal) {
    const num = parseInt(newVal, 10);
    if (!isNaN(num) && num > 0 && num <= store.totalQuestions) {
        questionNumber.value = num;
        store.currentQuestionIndex = num - 1;
        selectedOption.value = null;
        freeText.value = '';
    }
}


watch(() => route.params.questionNumber, (newVal) => {
    if (newVal) {
        updateQuestionState(newVal);
    }
})

onMounted(async () => {
    if (store.questions.length === 0) {
        await store.fetchQuestions();
    }
    updateQuestionState(route.params.questionNumber || '1');
});


function handleNext() {
  if (selectedOption.value!== null && currentQuestion.value) {
    store.recordAnswer(
      currentQuestion.value.id, 
      selectedOption.value, 
      freeText.value,
      currentQuestion.value.trait,
      currentQuestion.value.question
    )
    store.nextQuestion()
  }
}
</script>

<template>
  <div class="card quiz-card" v-if="currentQuestion">
    <ProgressBar />
    <div class="question-header">
      <span class="question-number">QUESTION {{ questionNumber }} / {{ store.totalQuestions }}</span>
      <h2>{{ currentQuestion.question }}</h2>
    </div>
    <div class="options">
      <label v-for="option in currentQuestion.options" :key="option.text" 
             :class="{ selected: selectedOption === option.score }">
        <input type="radio" :value="option.score" v-model="selectedOption">
        <span>{{ option.text }}</span>
      </label>
    </div>
    
    <div class="free-text-area">
        <label :for="'free-text-' + currentQuestion.id">{{ currentQuestion.free_text_prompt }}</label>
        <textarea :id="'free-text-' + currentQuestion.id" v-model="freeText" rows="4" placeholder="具体的なエピソードや考えを自由にお書きください。（任意）"></textarea>
    </div>

    <button @click="handleNext" :disabled="selectedOption === null">次へ</button>
  </div>
   <div v-else class="card">
    <p>質問を読み込んでいます...</p>
  </div>
</template>

<style scoped>
.quiz-card {
  width: 600px;
  max-width: 90%;
}
.question-header {
  margin-bottom: 30px;
}
.question-number {
  font-size: 0.8rem;
  color: #888;
  font-weight: bold;
}
h2 {
  margin-top: 10px;
  font-size: 1.5rem;
}
.options {
  display: flex;
  flex-direction: column;
  gap: 15px;
  margin-bottom: 30px;
}
.options label {
  display: block;
  padding: 15px;
  border: 1px solid #ddd;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease-in-out;
}
.options label:hover {
  background-color: #f5f5f5;
}
.options label.selected {
  border-color: #007bff;
  background-color: #e7f3ff;
  font-weight: bold;
}
.options input[type="radio"] {
  display: none;
}
.free-text-area {
    margin-bottom: 30px;
}
.free-text-area label {
    display: block;
    margin-bottom: 10px;
    font-weight: bold;
    color: #555;
}
.free-text-area textarea {
    width: 100%;
    padding: 10px;
    border: 1px solid #ccc;
    border-radius: 8px;
    font-size: 1rem;
    font-family: inherit;
    box-sizing: border-box; /* paddingを含めた幅計算に */
}
</style>
