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

  async function analyzeFreeTextAnswers() {
    isAnalyzing.value = true;
    // 全ての回答を分析対象とする
    const answersToAnalyze = Object.entries(userAnswers.value);
    
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
            question: answer.question,
            base_score: answer.score, // 選択式のスコアも送信
            question_id: questionId
          }),
        });
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        const result = await response.json();
        // result は { analyzed_score, explanation } を持つ
        analyzedScores.value[questionId] = { 
            score: result.analyzed_score, 
            explanation: result.explanation 
        };
      } catch (error) {
        console.error(`Failed to analyze text for question ${questionId}:`, error);
        // エラー時も同じ構造を保つ
        analyzedScores.value[questionId] = { score: answer.score, explanation: "分析中にエラーが発生しました。" };
      }
    });

    await Promise.all(analysisPromises);
    isAnalyzing.value = false;
  }

    const finalResult = computed(() => {
    if (isAnalyzing.value || Object.keys(userAnswers.value).length !== totalQuestions.value) {
      return null;
    }

    const answersWithFinalScores = questions.value.map(q => {
      const userAnswer = userAnswers.value[q.id];
      const analyzedResult = analyzedScores.value[q.id];
      
      let finalScore;
      let explanation;

      if (analyzedResult) {
        // 自由記述があった場合、分析結果を優先するが、スコアは選択式と平均する
        if (userAnswer.freeText.trim() !== '') {
          finalScore = (userAnswer.score + analyzedResult.score) / 2;
          explanation = analyzedResult.explanation;
        } else {
          // 自由記述がない場合は、分析された解説と選択式のスコアを使う
          finalScore = userAnswer.score;
          explanation = analyzedResult.explanation;
        }
      } else {
        // 分析がなかった場合（エラーなど）
        finalScore = userAnswer.score;
        explanation = "この回答のAIによる追加分析はありません。";
      }
      
      return {
        question: q.question,
        finalScore,
        explanation
      };
    });

    const traitScores = questions.value.reduce((acc, q) => {
        if (!acc[q.trait]) {
            acc[q.trait] = { total: 0, count: 0 };
        }
        const answer = answersWithFinalScores.find(a => a.question === q.question);
        if (answer) {
            acc[q.trait].total += answer.finalScore;
            acc[q.trait].count++;
        }
        return acc;
    }, {});

    const averagedTraitScores = Object.entries(traitScores).reduce((acc, [trait, data]) => {
        acc[trait] = data.count > 0 ? data.total / data.count : 0;
        return acc;
    }, {});

    const overallAverage = Object.values(averagedTraitScores).reduce((sum, score) => sum + score, 0) / Object.keys(averagedTraitScores).length;

    const resultTypeDetails = getResultType(overallAverage);

    return {
      title: resultTypeDetails.title,
      description: resultTypeDetails.description,
      plans: resultTypeDetails.plans,
      scoreDetails: {
        average: overallAverage.toFixed(2),
        traitScores: averagedTraitScores,
        answers: answersWithFinalScores
      }
    };
  });

  function getResultType(averageScore) {
    if (averageScore >= 3.2) {
      return {
        title: "超冒険家",
        description: "あなたは未知なる体験を追い求める、真の冒険家です。既成概念にとらわれず、自分だけの道を開拓していく旅をこよなく愛します。予測不可能な出来事さえも楽しむことができるでしょう。",
        plans: [
          { title: "秘境探検", description: "アマゾンの奥地やパプアニューギニアの村など、文明から離れた場所でのサバイバル体験。" },
          { title: "ヒッチハイクの旅", description: "目的地だけを決め、現地での出会いに身を任せる自由な旅。" },
          { title: "山脈越え", description: "アンデス山脈やヒマラヤ山脈など、厳しい自然環境を自らの足で踏破するチャレンジ。" }
        ]
      };
    } else if (averageScore >= 2.5) {
      return {
        title: "探求的トラベラー",
        description: "あなたは好奇心旺盛で、新しい発見を求める探求的な旅行者です。定番の観光地だけでなく、少し変わった体験や現地の人との交流を大切にします。計画と即興のバランスが取れた旅を好みます。",
        plans: [
          { title: "文化体験の旅", description: "タイの料理教室に参加したり、スペインでフラメンコを習ったりする、現地の文化に深く触れる旅。" },
          { title: "地方都市巡り", description: "首都だけでなく、その国の魅力的な地方都市を鉄道で巡る旅。" },
          { title: "ロードトリップ", description: "アメリカのルート66やアイスランドのリングロードなど、自由気ままな車の旅。" }
        ]
      };
    } else if (averageScore >= 1.8) {
      return {
        title: "バランス型ツーリスト",
        description: "あなたは快適さと新しい体験のバランスを重視する旅行者です。有名な観光スポットを楽しみつつ、時には自分だけの時間やリラックスも大切にします。事前の計画で、安心して旅を楽しみたいタイプです。",
        plans: [
          { title: "都市とリゾートの組み合わせ", description: "イタリアの都市観光とアマルフィ海岸でのリラックスを組み合わせるなど、多様な楽しみ方ができる旅。" },
          { title: "テーマのある旅", description: "フランスのワイナリー巡りや、ニュージーランドの映画ロケ地巡りなど、興味のあるテーマを深掘りする旅。" },
          { title: "オールインクルーシブ・リゾート", description: "カリブ海やモルディブのリゾートで、何も考えずに贅沢な時間を過ごす旅。" }
        ]
      };
    } else {
      return {
        title: "堅実派トラベラー",
        description: "あなたは安全性と快適さを第一に考える、堅実な旅行者です。実績のあるツアーや評価の高いホテルを選び、計画通りに旅を進めることを好みます。リラックスして、心身をリフレッシュすることが旅の主な目的です。",
        plans: [
          { title: "豪華客船クルーズ", description: "地中海やアラスカなど、移動や食事の心配なく絶景を楽しめるクルーズの旅。" },
          { title: "温泉リゾート滞在", description: "日本の温泉地やヨーロッパのスパリゾートで、日頃の疲れを癒すウェルネス志向の旅。" },
          { title: "ガイド付き周遊ツアー", description: "専門ガイドが案内してくれる、歴史や文化を効率よく学べるパッケージツアー。" }
        ]
      };
    }
  }

  return {
    questions,
    userAnswers,
    currentQuestionIndex,
    totalQuestions,
    progress,
    fetchQuestions,
    recordAnswer,
    nextQuestion,
    resetQuiz,
    isAnalyzing,
    analyzeFreeTextAnswers,
    finalResult
  }
})
;

