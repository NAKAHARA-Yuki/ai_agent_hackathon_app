import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from './authStore'

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

  const analyzedScores = ref({})
  const isAnalyzing = ref(false)
  const aiPlans = ref(null)
  const isGeneratingPlans = ref(false)
  const isProcessing = ref(false) // 終了処理（分析+プラン生成+保存）中
  const isSavingProfile = ref(false)
  const processingStage = ref('idle') // idle|analyzing|scoring|parallel|done|error
  const processingPercent = computed(() => {
    switch (processingStage.value) {
      case 'idle': return 0
      case 'analyzing': return isAnalyzing.value ? 35 : 50
      case 'scoring': return 65
      case 'parallel': return (isGeneratingPlans.value || isSavingProfile.value) ? 85 : 95
      case 'done': return 100
      case 'error': return 100
      default: return 0
    }
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

  async function nextQuestion() {
    if (currentQuestionIndex.value < totalQuestions.value - 1) {
      currentQuestionIndex.value++
      router.push({ name: 'question', params: { questionNumber: currentQuestionIndex.value + 1 } })
    } else {
      // 最後の質問が終わったら処理専用画面へ遷移して可視化
      currentQuestionIndex.value++ // プログレス100%
      isProcessing.value = true
      processingStage.value = 'analyzing'
      router.push({ name: 'processing' })
      // 処理は専用フローで実行
      runProcessingFlow()
    }
  }

  function resetQuiz() {
    userAnswers.value = {}
    currentQuestionIndex.value = 0
  analyzedScores.value = {}
  aiPlans.value = null
  }


  // APIからの説明文がオブジェクトやJSON文字列で返る場合に備えて統一する
  function normalizeExplanation(raw) {
    try {
      if (raw == null) return '';
      if (typeof raw === 'object') {
        if (typeof raw.explanation === 'string') return raw.explanation;
        if (typeof raw['解説'] === 'string') return raw['解説'];
        return JSON.stringify(raw);
      }
      const s = String(raw).trim();
      // JSON文字列っぽい場合はパースして説明を抽出
      if ((s.startsWith('{') && s.endsWith('}')) || (s.startsWith('[') && s.endsWith(']'))) {
        try {
          const parsed = JSON.parse(s);
          if (parsed && typeof parsed === 'object') {
            if (typeof parsed.explanation === 'string') return parsed.explanation;
            if (typeof parsed['解説'] === 'string') return parsed['解説'];
            return JSON.stringify(parsed);
          }
        } catch (_) { /* no-op */ }
      }
      if ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'"))) {
        return s.slice(1, -1);
      }
      return s;
    } catch (_) {
      return String(raw);
    }
  }

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
    // result は { analyzed_score, explanation } または explanationがオブジェクト/JSON文字列の場合あり
    analyzedScores.value[questionId] = { 
      score: result.analyzed_score, 
      explanation: normalizeExplanation(result.explanation ?? result)
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
        if (userAnswer && typeof userAnswer.freeText === 'string' && userAnswer.freeText.trim() !== '') {
          finalScore = (userAnswer.score + analyzedResult.score) / 2;
          explanation = normalizeExplanation(analyzedResult.explanation);
        } else {
          // 自由記述がない場合は、分析された解説と選択式のスコアを使う
          finalScore = userAnswer.score;
          explanation = normalizeExplanation(analyzedResult.explanation);
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
      plans: aiPlans.value ?? resultTypeDetails.plans,
      scoreDetails: {
        average: overallAverage.toFixed(2),
        traitScores: averagedTraitScores,
        answers: answersWithFinalScores
      }
    };
  });

  async function generateAIPlans() {
    try {
      const current = finalResult.value;
      if (!current) return; // 分析未完了
      isGeneratingPlans.value = true;
      const resp = await fetch('/api/generate_plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ travel_type: current.title, description: current.description })
      });
      if (!resp.ok) throw new Error('Failed to generate AI plans');
      const data = await resp.json();
      if (Array.isArray(data?.plans)) {
        aiPlans.value = data.plans;
      } else {
        aiPlans.value = [{ title: '生成エラー', description: 'AIプランの形式が不正でした。' }];
      }
    } catch (e) {
      console.error('generateAIPlans error:', e);
      aiPlans.value = [{ title: 'エラー', description: 'AIプランの生成に失敗しました。時間をおいて再試行してください。' }];
    } finally {
      isGeneratingPlans.value = false;
    }
  }

  async function runProcessingFlow() {
    try {
      // 1) 回答解析（全自由記述＋選択肢ベース補足）
      processingStage.value = 'analyzing'
      await analyzeFreeTextAnswers()

      // 2) スコア集計（computedが反映されるのを待つ）
      processingStage.value = 'scoring'
      await new Promise(r => setTimeout(r, 150))

      // 3) プラン生成とプロフィール保存を並列に実行
      processingStage.value = 'parallel'
      isSavingProfile.value = true
      await Promise.all([
        (async () => { await generateAIPlans() })(),
        (async () => { try { await savePersonaProfile() } finally { isSavingProfile.value = false } })()
      ])

      // 完了
      processingStage.value = 'done'
      isProcessing.value = false
      // 結果画面へ
      router.replace({ name: 'results' })
    } catch (e) {
      console.error('runProcessingFlow error:', e)
      processingStage.value = 'error'
      isProcessing.value = false
      router.replace({ name: 'results' })
    }
  }

  // 診断プロフィールをサーバーに保存し、ペルソナのシステムプロンプトを生成
  async function savePersonaProfile() {
    try {
      const current = finalResult.value;
      if (!current) return;
      const auth = useAuthStore();
      const payload = {
        profile: {
          title: current.title,
          description: current.description,
          traitScores: current.scoreDetails?.traitScores || {}
        }
      };
      const resp = await fetch('/api/persona', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...auth.authHeader() },
        body: JSON.stringify(payload)
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        console.error('savePersonaProfile failed:', err);
      }
    } catch (e) {
      console.error('savePersonaProfile error:', e);
    }
  }

  function getResultType(averageScore) {
    if (averageScore >= 3.2) {
      return {
        title: "超冒険家",
        description: "あなたは未知なる体験を追い求める、真の冒険家です。既成概念にとらわれず、自分だけの道を開拓していく旅をこよなく愛します。予測不可能な出来事さえも楽しむことができるでしょう。",
        plans: [
          { title: "屋久島 縦走トレッキング", description: "白谷雲水峡〜縄文杉エリアを含む縦走。現地ガイド同行で安全確保しつつ手付かずの森を体感。" },
          { title: "知床 冬の流氷アドベンチャー", description: "ドライスーツでの流氷ウォークや流氷カヤック。ワシ・アザラシ観察も組み込む。" },
          { title: "小笠原 エコツアー滞在", description: "父島でのドルフィンスイムと山歩き。固有種の自然保護に配慮した少人数ツアー参加。" }
        ]
      };
    } else if (averageScore >= 2.5) {
      return {
        title: "探求的トラベラー",
        description: "あなたは好奇心旺盛で、新しい発見を求める探求的な旅行者です。定番の観光地だけでなく、少し変わった体験や現地の人との交流を大切にします。計画と即興のバランスが取れた旅を好みます。",
        plans: [
          { title: "瀬戸内アートアイランド巡り", description: "直島・豊島・犬島をフェリーで周遊。ベネッセハウス、家プロジェクト、豊島美術館を効率よく鑑賞。" },
          { title: "金沢・加賀 伝統工芸体験", description: "金箔貼りや九谷焼の絵付けに挑戦。ひがし茶屋街の文化散策と地元食を楽しむ。" },
          { title: "四国遍路ハイライトウォーク", description: "初心者向け区間を日帰りまたは1泊で歩く。道後温泉やご当地グルメも組み合わせ。" }
        ]
      };
    } else if (averageScore >= 1.8) {
      return {
        title: "バランス型ツーリスト",
        description: "あなたは快適さと新しい体験のバランスを重視する旅行者です。有名な観光スポットを楽しみつつ、時には自分だけの時間やリラックスも大切にします。事前の計画で、安心して旅を楽しみたいタイプです。",
        plans: [
          { title: "東京＋箱根 王道と温泉", description: "都内の定番スポットを抑えた後、箱根で温泉と美術館（彫刻の森・ポーラ）でゆったり。" },
          { title: "京都 定番＋郊外散策", description: "清水寺・伏見稲荷に加え、宇治や大原へ足を延ばして自然と寺院の調和を味わう。" },
          { title: "福岡 食と糸島ドライブ", description: "屋台やローカルグルメを楽しみ、糸島で海辺カフェや軽いハイキングを満喫。" }
        ]
      };
    } else {
      return {
        title: "堅実派トラベラー",
        description: "あなたは安全性と快適さを第一に考える、堅実な旅行者です。実績のあるツアーや評価の高いホテルを選び、計画通りに旅を進めることを好みます。リラックスして、心身をリフレッシュすることが旅の主な目的です。",
        plans: [
          { title: "草津・箱根・由布院 温泉リゾート滞在", description: "客室露天やスパ付き宿で連泊し、移動を最小限にしてゆったり過ごす。" },
          { title: "瀬戸内 内航クルーズ（国内）", description: "瀬戸内海の多島美を船で巡る。寄港地観光はガイド付きで安心。" },
          { title: "日光・鎌倉 定番史跡のガイドツアー", description: "世界遺産や名刹を専門ガイドと巡り、文化や歴史を効率よく学ぶ。" }
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
  finalResult,
  aiPlans,
  isGeneratingPlans,
  isProcessing,
  isSavingProfile,
  processingStage,
  processingPercent,
  generateAIPlans,
  savePersonaProfile,
  runProcessingFlow,
  }
})
;

