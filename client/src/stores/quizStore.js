import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'

export const useQuizStore = defineStore('quiz', () => {
  const router = useRouter()
  const questions = ref([])
  // 回答を { questionId: { score: 1, freeText: "..." } } の形式で保存
  const userAnswers = ref({})
  const currentQuestionIndex = ref(0)

  const totalQuestions = computed(() => questions.value.length)
  const progress = computed(() => {
    if (!questions.value || totalQuestions.value === 0) return 0
    // 最後の結果ページでは100%にするため、+1する
    return ((currentQuestionIndex.value) / totalQuestions.value) * 100
  })

  async function fetchQuestions() {
    try {
      const response = await fetch('/api/questions')
      if (!response.ok) {
        throw new Error('Network response was not ok')
      }
      questions.value = await response.json()
      resetQuiz()
    } catch (error) {
      console.error('Failed to fetch questions:', error)
    }
  }

  function recordAnswer(questionId, score, freeText, trait, question) {
    userAnswers.value[questionId] = { score, freeText, trait, question }
  }

  function nextQuestion() {
    if (currentQuestionIndex.value < totalQuestions.value - 1) {
      currentQuestionIndex.value++
      router.push({ name: 'question', params: { questionNumber: currentQuestionIndex.value + 1 } })
    } else {
      // 最後の質問が終わったら結果ページへ
      currentQuestionIndex.value++ // プログレスバーを100%にするため
      router.push({ name: 'results' })
    }
  }

  function resetQuiz() {
    userAnswers.value = {}
    currentQuestionIndex.value = 0
  }

  const analyzedScores = ref({});
  const isAnalyzing = ref(false);

  // ... (fetchQuestions, recordAnswer, nextQuestion, resetQuizは変更なし) ...

  async function analyzeFreeTextAnswers() {
    isAnalyzing.value = true;
    const answersToAnalyze = Object.entries(userAnswers.value).filter(([, answer]) => answer.freeText.trim() !== '');
    
    const analysisPromises = answersToAnalyze.map(async ([questionId, answer]) => {
      try {
        const response = await fetch('/api/analyze', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            text: answer.freeText,
            trait: answer.trait,
            question: answer.question
          }),
        });
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        const result = await response.json();
        analyzedScores.value[questionId] = result.analyzed_score;
      } catch (error) {
        console.error(`Failed to analyze text for question ${questionId}:`, error);
        analyzedScores.value[questionId] = 0; // エラーの場合はスコア0
      }
    });

    await Promise.all(analysisPromises);
    isAnalyzing.value = false;
  }

  const resultType = computed(() => {
    if (Object.keys(userAnswers.value).length === 0) {
      return { title: '診断中...', description: '結果を計算しています。' }
    }
    const totalScore = Object.values(userAnswers.value).reduce((sum, answer) => sum + answer.score, 0)
    const averageScore = totalQuestions.value > 0 ? totalScore / totalQuestions.value : 0

    if (averageScore >= 3.2) {
      return {
        title: '冒険型 (アロセントリック)',
        description: 'あなたは未知なるものへの探求心が強く、型にはまらない本物の体験を求める冒険家です。観光地化されていない場所や、現地の人々との深い交流に価値を見出します。'
      }
    } else if (averageScore >= 2.2) {
      return {
        title: '中間型 (ミッドセントリック)',
        description: 'あなたは冒険と安定のバランスが取れた旅行者です。有名な観光地を楽しみつつも、時には少し外れた場所へ足を延ばす柔軟性を持っています。'
      }
    } else {
      return {
        title: '依存型 (サイコセントリック)',
        description: 'あなたは慣れ親しんだ環境での安心感と快適さを重視します。事前に計画された旅程や、サービスの整った人気の観光地でリラックスすることを好みます。'
      }
    }
  });

  const finalResult = computed(() => {
    if (Object.keys(userAnswers.value).length !== totalQuestions.value || totalQuestions.value === 0) {
        return { title: '診断中...', description: '結果を計算しています。' };
    }

    let totalScore = 0;
    let scoreCount = 0;

    Object.entries(userAnswers.value).forEach(([questionId, answer]) => {
        const analyzedScore = analyzedScores.value[questionId];
        // 自由記述の分析結果があればそちらを優先し、なければ選択式のスコアを使う
        if (analyzedScore && analyzedScore > 0) {
            totalScore += analyzedScore;
        } else {
            totalScore += answer.score;
        }
        scoreCount++;
    });

    const averageScore = scoreCount > 0 ? totalScore / scoreCount : 0;

    if (averageScore >= 3.2) {
      return {
        title: '冒険型 (アロセントリック)',
        description: 'あなたは未知なるものへの探求心が強く、型にはまらない本物の体験を求める冒険家です。観光地化されていない場所や、現地の人々との深い交流に価値を見出します。'
      }
    } else if (averageScore >= 2.2) {
      return {
        title: '中間型 (ミッドセントリック)',
        description: 'あなたは冒険と安定のバランスが取れた旅行者です。有名な観光地を楽しみつつも、時には少し外れた場所へ足を延ばす柔軟性を持っています。'
      }
    } else {
      return {
        title: '依存型 (サイコセントリック)',
        description: 'あなたは慣れ親しんだ環境での安心感と快適さを重視します。事前に計画された旅程や、サービスの整った人気の観光地でリラックスすることを好みます。'
      }
    }
  });

  return { 
    questions, 
    userAnswers, 
    currentQuestionIndex,
    totalQuestions,
    progress,
    finalResult,
    isAnalyzing,
    fetchQuestions, 
    recordAnswer, 
    nextQuestion,
    resetQuiz,
    analyzeFreeTextAnswers
  }
})
