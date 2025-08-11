<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuizStore } from '@/stores/quizStore'
import ProgressBar from '@/components/ProgressBar.vue'
import BackButton from '@/components/BackButton.vue'

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


const isFreeTextSelected = computed(() => selectedOption.value === 0);

function handleNext() {
  if (selectedOption.value !== null && currentQuestion.value) {
    // 自由記述が選択されたが、何も書かれていない場合は進めない
    if (isFreeTextSelected.value && freeText.value.trim() === '') {
        alert('自由記述欄に回答を入力してください。');
        return;
    }

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
  <main class="question-view">
    <transition name="fade" mode="out-in">
      <div class="card quiz-card" :key="questionNumber" v-if="currentQuestion">
        <BackButton />
        <ProgressBar />
        <div class="question-header">
          <span class="question-number">QUESTION {{ questionNumber }} / {{ store.totalQuestions }}</span>
          <h2>{{ currentQuestion.question }}</h2>
        </div>
        <div class="options">
          <label v-for="option in currentQuestion.options" :key="option.text" 
                 :class="{ selected: selectedOption === option.score }">
            <input type="radio" :value="option.score" v-model="selectedOption">
            <span class="option-text">{{ option.text }}</span>
          </label>
        </div>
        
        <transition name="fade">
          <div class="free-text-area" v-if="isFreeTextSelected">
              <label :for="'free-text-' + currentQuestion.id">{{ currentQuestion.free_text_prompt }}</label>
              <textarea :id="'free-text-' + currentQuestion.id" v-model="freeText" rows="4" :placeholder="currentQuestion.free_text_placeholder"></textarea>
          </div>
        </transition>

        <button @click="handleNext" :disabled="selectedOption === null">次へ</button>
      </div>
      <div v-else class="card">
        <p>質問を読み込んでいます...</p>
      </div>
    </transition>
  </main>
</template>

<style scoped>
.question-view { display:grid; place-items:center; height:100%; padding:16px; width:100%; overflow:auto; }
.quiz-card {
  width: min(720px, 100%);
  box-sizing: border-box;
}
.question-header {
  margin-bottom: 30px;
  text-align: center;
}
.question-number {
  font-size: 0.9rem;
  color: #888;
  font-weight: 700;
  letter-spacing: 1px;
}
h2 {
  margin-top: 10px;
  font-size: 1.8rem;
  color: #1a237e;
}
.options {
  display: grid;
  grid-template-columns: 1fr;
  gap: 15px;
  margin-bottom: 30px;
}
.options label {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  width: 100%;
  padding: 20px;
  border: 2px solid transparent;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.3s ease;
  background-color: rgba(255, 255, 255, 0.6);
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
}
.options label:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 10px rgba(0,0,0,0.1);
}
.options label.selected {
  border-color: #ff4b2b;
  background-color: #fff;
  font-weight: bold;
  box-shadow: 0 4px 15px rgba(255, 75, 43, 0.3);
}
.options input[type="radio"] {
  display: none;
}
.option-text {
  font-size: 1.1rem;
  flex: 1 1 auto;
  min-width: 0;
  line-height: 1.5;
  word-break: break-word;
  overflow-wrap: anywhere;
  white-space: normal;
}

.free-text-area {
    margin: 20px 0 30px;
}
.free-text-area label {
    display: block;
    margin-bottom: 10px;
    font-weight: bold;
    color: #1a237e;
    text-align: center;
}
.free-text-area textarea {
    width: 100%;
    padding: 15px;
    border: 1px solid #ccc;
    border-radius: 10px;
    font-size: 1rem;
    font-family: inherit;
    box-sizing: border-box;
    transition: border-color 0.3s, box-shadow 0.3s;
}
.free-text-area textarea:focus {
    outline: none;
    border-color: #ff4b2b;
    box-shadow: 0 0 0 3px rgba(255, 75, 43, 0.2);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* モバイル向け微調整 */
@media (max-width: 600px) {
  h2 { font-size: 1.35rem; margin-top: 6px; }
  .question-header { margin-bottom: 20px; }
  .options { gap: 12px; margin-bottom: 20px; }
  .options label { padding: 14px; }
  .free-text-area { margin: 14px 0 20px; }
  .free-text-area textarea { font-size: 16px; } /* モバイルでのタップしやすさ */
  button { width: 100%; padding: 12px; }
}
</style>
