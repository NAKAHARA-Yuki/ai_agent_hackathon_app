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
  // 好きなこと（Spotifyライク）選択用
  const selectedLikes = ref([])
  // デフォルトの候補（APIフォールバック用）
  const DEFAULT_LIKES_OPTIONS = [
    // weights は正規化タグ: novelty, pace, budget, social, culture, nature, gourmet, planning, comfort, activity, risk, digital
    // ベース
    { id: 'onsen', label: '温泉・サウナ', emoji: '♨️', weights: { comfort: +0.6, pace: -0.2 } },
    { id: 'relax', label: 'リラックス・スパ', emoji: '🧖', weights: { comfort: +0.8, activity: -0.4, pace: -0.4 } },
    { id: 'art', label: 'アート・美術館', emoji: '🖼️', weights: { culture: +0.7, novelty: +0.1 } },
    { id: 'history', label: '歴史・世界遺産', emoji: '🏛️', weights: { culture: +0.8 } },
    { id: 'nature', label: '自然・絶景', emoji: '🏞️', weights: { nature: +0.8, activity: +0.2 } },
    { id: 'gourmet', label: 'グルメ・食べ歩き', emoji: '🍣', weights: { gourmet: +0.8, comfort: +0.1 } },
    { id: 'citywalk', label: 'まち歩き', emoji: '🚶', weights: { activity: +0.4, culture: +0.2 } },
    { id: 'adventure', label: 'アドベンチャー', emoji: '🧗', weights: { novelty: +0.6, risk: +0.4, activity: +0.6 } },
    { id: 'themepark', label: 'テーマパーク', emoji: '🎢', weights: { comfort: +0.2, pace: +0.2 } },
    { id: 'island', label: '離島ステイ', emoji: '🏝️', weights: { nature: +0.6, novelty: +0.3, comfort: +0.2 } },
    { id: 'snow', label: '雪・ウィンター', emoji: '❄️', weights: { activity: +0.4, risk: +0.2, comfort: -0.1 } },
    { id: 'festival', label: '祭り・イベント', emoji: '🎊', weights: { social: +0.6, culture: +0.2 } },

    // リクエストの追加カテゴリ
    { id: 'pilgrimage', label: '聖地巡礼（アニメ・ドラマ）', emoji: '🎬', weights: { culture: +0.5, novelty: +0.3, planning: +0.2 } },
    { id: 'cafe', label: 'カフェめぐり', emoji: '☕', weights: { gourmet: +0.6, comfort: +0.2, pace: -0.1 } },
    { id: 'coffee', label: 'コーヒー巡り', emoji: '☕', weights: { gourmet: +0.5, comfort: +0.2, pace: -0.1 } },
    { id: 'sweets', label: 'スイーツ巡り', emoji: '🍰', weights: { gourmet: +0.5, comfort: +0.2 } },
    { id: 'bakery', label: 'ベーカリー巡り', emoji: '�', weights: { gourmet: +0.4, comfort: +0.2, pace: -0.1 } },
    { id: 'bakery', label: 'ベーカリー巡り', emoji: '�', weights: { gourmet: +0.4, comfort: +0.2, pace: -0.1 } },
    { id: 'sushi_love', label: '寿司巡り', emoji: '🍣', weights: { gourmet: +0.5 } },
    { id: 'wagashi', label: '和菓子', emoji: '🍡', weights: { gourmet: +0.4, culture: +0.2 } },
    { id: 'craftbeer', label: 'クラフトビール', emoji: '🍺', weights: { gourmet: +0.4, social: +0.3 } },
    { id: 'wine', label: 'ワイン', emoji: '🍷', weights: { gourmet: +0.4, comfort: +0.2 } },
    { id: 'sake', label: '日本酒', emoji: '🍶', weights: { gourmet: +0.4, culture: +0.2 } },
    { id: 'vegan', label: 'ヴィーガン対応', emoji: '🥦', weights: { gourmet: +0.2, planning: +0.2, comfort: +0.1 } },

    { id: 'shrines', label: '神社仏閣', emoji: '⛩️', weights: { culture: +0.6, pace: -0.1 } },
    { id: 'goshuin', label: '御朱印集め', emoji: '📖', weights: { culture: +0.5, planning: +0.2 } },
    { id: 'castles', label: '城めぐり', emoji: '🏯', weights: { culture: +0.6, activity: +0.2 } },
    { id: 'hanabi', label: '花火', emoji: '🎆', weights: { social: +0.3, culture: +0.2 } },
    { id: 'sakura', label: '桜', emoji: '🌸', weights: { nature: +0.4, culture: +0.2 } },
    { id: 'momiji', label: '紅葉', emoji: '🍁', weights: { nature: +0.5, activity: +0.1, pace: -0.1 } },
    { id: 'waterfalls', label: '滝めぐり', emoji: '�', weights: { nature: +0.6, activity: +0.3, risk: +0.1 } },
    { id: 'waterfalls', label: '滝めぐり', emoji: '�️', weights: { nature: +0.6, activity: +0.3, risk: +0.1 } },
    { id: 'nightview', label: '夜景・イルミ', emoji: '🌃', weights: { culture: +0.2, novelty: +0.1, comfort: +0.1 } },
    { id: 'aquarium', label: '水族館', emoji: '🐠', weights: { culture: +0.2, comfort: +0.2 } },
    { id: 'zoo', label: '動物園・牧場', emoji: '🦁', weights: { nature: +0.3, social: +0.2 } },

    { id: 'kids', label: '子連れに優しい', emoji: '👨‍👩‍👧', weights: { comfort: +0.4, risk: +0.2, pace: -0.2 } },
    { id: 'pet', label: 'ペット同伴OK', emoji: '🐶', weights: { comfort: +0.2, planning: +0.2, nature: +0.2 } },
    { id: 'couple', label: 'カップル向け', emoji: '💑', weights: { comfort: +0.2, gourmet: +0.2, pace: -0.1 } },
    { id: 'girls', label: '女子旅', emoji: '👭', weights: { gourmet: +0.3, culture: +0.2 } },
    { id: 'solo', label: 'ひとり旅', emoji: '🧍', weights: { novelty: +0.2, planning: +0.1, comfort: -0.1 } },
    { id: 'photography', label: '写真撮影', emoji: '📸', weights: { nature: +0.3, culture: +0.2, planning: +0.1 } },
    { id: 'instaspot', label: '映えスポット', emoji: '✨', weights: { digital: +0.3, novelty: +0.2, culture: +0.1 } },

    // アクティビティ系
    { id: 'surf', label: 'サーフィン', emoji: '🏄', weights: { activity: +0.7, risk: +0.3, nature: +0.3 } },
    { id: 'sup', label: 'SUP・カヤック', emoji: '🛶', weights: { activity: +0.6, nature: +0.3 } },
    { id: 'snorkel', label: 'シュノーケリング', emoji: '🤿', weights: { activity: +0.6, nature: +0.4 } },
    { id: 'ski', label: 'スキー・スノボ', emoji: '🎿', weights: { activity: +0.7, risk: +0.3, nature: +0.3 } },
    { id: 'hike', label: 'ハイキング', emoji: '🥾', weights: { activity: +0.5, nature: +0.5 } },
    { id: 'climb', label: '登山', emoji: '⛰️', weights: { activity: +0.7, risk: +0.3, nature: +0.4 } },
    { id: 'trailrun', label: 'トレイルラン', emoji: '🏃‍♂️', weights: { activity: +0.7, risk: +0.2, nature: +0.3 } },
    { id: 'cycle', label: 'サイクリング', emoji: '🚴', weights: { activity: +0.5, nature: +0.3 } },
    { id: 'drive', label: 'ドライブ', emoji: '🚗', weights: { comfort: +0.2, activity: +0.2 } },

    // 乗り物・移動
    { id: 'rail', label: '鉄道旅', emoji: '🚆', weights: { culture: +0.2, planning: +0.3, comfort: +0.1 } },
    { id: 'scenic_train', label: '絶景列車', emoji: '🚞', weights: { nature: +0.3, comfort: +0.2 } },
    { id: 'ferry', label: 'フェリー旅', emoji: '⛴️', weights: { comfort: +0.2, nature: +0.2 } },
    { id: 'cruise', label: 'クルーズ', emoji: '🚢', weights: { comfort: +0.6, pace: -0.2 } },

    // 体験・文化
    { id: 'craft', label: '伝統工芸体験', emoji: '🎎', weights: { culture: +0.6, novelty: +0.2, activity: +0.1 } },
    { id: 'pottery', label: '陶芸体験', emoji: '🏺', weights: { culture: +0.5, activity: +0.2 } },
    { id: 'kintsugi', label: '金継ぎ', emoji: '🪡', weights: { culture: +0.5, planning: +0.2 } },
    { id: 'dyeing', label: '染物体験', emoji: '🧶', weights: { culture: +0.5 } },
    { id: 'sushi_making', label: '寿司握り体験', emoji: '🍣', weights: { gourmet: +0.4, culture: +0.3, activity: +0.1 } },
    { id: 'tea', label: '茶道・抹茶体験', emoji: '🍵', weights: { culture: +0.6, pace: -0.2 } },
    { id: 'kimono', label: '着物レンタル', emoji: '👘', weights: { culture: +0.5, digital: +0.1 } },
    { id: 'markets', label: '朝市・市場', emoji: '🧺', weights: { gourmet: +0.4, culture: +0.2, pace: +0.1 } },
    { id: 'outlet', label: 'アウトレット・ショッピング', emoji: '🛍️', weights: { budget: +0.3, comfort: +0.2 } },
    { id: 'thrift', label: '古着・蚤の市', emoji: '👗', weights: { budget: +0.2, novelty: +0.2, culture: +0.2 } },
    { id: 'tech', label: 'テック・ガジェット巡り', emoji: '📱', weights: { digital: +0.6, novelty: +0.2 } },
    { id: 'science_museum', label: '科学館・博物館', emoji: '🧪', weights: { culture: +0.5 } },
    { id: 'concept_cafe', label: 'コンセプトカフェ', emoji: '🧋', weights: { social: +0.2, culture: +0.2, novelty: +0.2 } },

    // ウェルネス
    { id: 'yoga', label: 'ヨガ・ウェルネス', emoji: '🧘', weights: { comfort: +0.6, activity: +0.2, pace: -0.3 } },
  ]
  // 実際にUIで使う候補（APIで置き換え可能）
  const likesOptionsState = ref(DEFAULT_LIKES_OPTIONS)
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
  // 最後の質問が終わったら「好きなこと」選択へ
  currentQuestionIndex.value++ // プログレス100%
  router.push({ name: 'interests' })
    }
  }

  function resetQuiz() {
    userAnswers.value = {}
    currentQuestionIndex.value = 0
  analyzedScores.value = {}
  aiPlans.value = null
  selectedLikes.value = []
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
    if (isAnalyzing.value || Object.keys(userAnswers.value).length === 0 || totalQuestions.value === 0 || Object.keys(userAnswers.value).length !== totalQuestions.value) {
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

    // 平均スコア（trait別）
    let averagedTraitScores = Object.entries(traitScores).reduce((acc, [trait, data]) => {
        acc[trait] = data.count > 0 ? data.total / data.count : 0;
        return acc;
    }, {});

    // 好きなことの選択を既存の trait キーにのみ加点
    if (Array.isArray(selectedLikes.value) && selectedLikes.value.length) {
      const clamp = (v) => Math.max(1, Math.min(4, v))
      // trait名から正規化タグを推定
      const guessTag = (key) => {
        const k = String(key).toLowerCase()
        if (/(novel|新規|冒険|venture)/.test(k)) return 'novelty'
        if (/(pace|密度|ペース)/.test(k)) return 'pace'
        if (/(budget|予算|価格|コスト|value)/.test(k)) return 'budget'
        if (/(social|交流|社交|人)/.test(k)) return 'social'
        if (/(culture|文化|歴史|history|heritage)/.test(k)) return 'culture'
        if (/(nature|自然|景観)/.test(k)) return 'nature'
        if (/(gourmet|食|グルメ|food)/.test(k)) return 'gourmet'
        if (/(planning|計画|綿密)/.test(k)) return 'planning'
        if (/(comfort|快適|amenity|ラグジュ)/.test(k)) return 'comfort'
        if (/(activity|活動|エナジ|energy|アクティ)/.test(k)) return 'activity'
        if (/(risk|安全|セーフ)/.test(k)) return 'risk'
        if (/(digital|テクノ|デジ)/.test(k)) return 'digital'
        return null
      }
      const weightsSumByTag = {}
      selectedLikes.value.forEach(id => {
        const opt = (likesOptionsState.value || []).find(o => o.id === id)
        if (!opt) return
        Object.entries(opt.weights || {}).forEach(([tag, w]) => {
          weightsSumByTag[tag] = (weightsSumByTag[tag] || 0) + w
        })
      })
      Object.keys(averagedTraitScores).forEach(traitKey => {
        const tag = guessTag(traitKey)
        if (!tag) return
        const w = weightsSumByTag[tag]
        if (!w) return
        // 影響を控えめに 0.2 係数で加点
        averagedTraitScores[traitKey] = clamp((averagedTraitScores[traitKey] || 0) + (w * 0.2))
      })
    }

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
  isProcessing.value = true
      // 1) 回答解析（全自由記述＋選択肢ベース補足）
      processingStage.value = 'analyzing'
      await analyzeFreeTextAnswers()

      // 2) スコア集計（computedが反映されるのを待つ）
      processingStage.value = 'scoring'
      await new Promise(r => setTimeout(r, 150))

      // 3) プラン生成とプロフィール保存を並列に実行
      processingStage.value = 'parallel'
      isSavingProfile.value = true
      
      const [
        generateAIPlansResult,
        savePersonaProfileResult,
        saveUserHobbiesResult
      ] = await Promise.allSettled([
        (async () => { await generateAIPlans() })(),
        (async () => { try { await savePersonaProfile() } finally { isSavingProfile.value = false } })(),
        (async () => { try { await saveUserHobbies() } catch(_) {} })()
      ])
      
      // Check if persona saving failed
      if (savePersonaProfileResult.status === 'rejected') {
        console.warn('Persona saving failed, but continuing with quiz completion:', savePersonaProfileResult.reason)
        // Note: We don't throw here to allow the user to see results even if saving failed
      }

  // 完了
  processingStage.value = 'done'
  isProcessing.value = false
  // 結果画面へ（結果を見た後にメインへ進める）
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
      if (!current) {
        console.warn('No final result available for persona profile saving');
        return;
      }
      const auth = useAuthStore();
    // hobbies を同時送信（サーバー側でプロンプトに反映される）
    const opts = Array.isArray(likesOptions.value) ? likesOptions.value : []
    const hobbies = (selectedLikes.value || []).map(id => opts.find(o => o.id === id)?.label || String(id)).filter(Boolean).slice(0, 10)
      const payload = {
        profile: {
          title: current.title,
          description: current.description,
      traitScores: current.scoreDetails?.traitScores || {},
      hobbies
        }
      };
      const resp = await fetch('/api/persona', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...auth.authHeader() },
        body: JSON.stringify(payload)
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ error: 'Unknown error' }));
        console.error('savePersonaProfile failed:', err);
        throw new Error(`Failed to save persona: ${err.error || 'Server error'}`);
      } else {
        console.log('Persona profile saved successfully');
      }
    } catch (e) {
      console.error('savePersonaProfile error:', e);
      throw e; // Re-throw to allow parent error handling
    }
  }

  // ユーザープロフィールに hobbies として保存
  async function saveUserHobbies() {
    try {
      const auth = useAuthStore();
      // id -> label に変換（最大10件に制限）
      const opts = Array.isArray(likesOptionsState.value) ? likesOptionsState.value : []
      const labels = (selectedLikes.value || []).map(id => {
        const found = opts.find(o => o.id === id)
        return found?.label || String(id)
      }).filter(Boolean).slice(0, 10)
      if (!labels.length) return
      const resp = await fetch('/api/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...auth.authHeader() },
        body: JSON.stringify({ profile: { hobbies: labels } })
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        console.error('saveUserHobbies failed:', err)
      }
    } catch (e) {
      console.error('saveUserHobbies error:', e)
    }
  }

  // 趣味マスタをAPIから取得
  async function fetchLikesOptions() {
    try {
      const resp = await fetch('/api/hobbies')
      if (!resp.ok) throw new Error('failed to fetch hobbies')
      const data = await resp.json()
      if (Array.isArray(data?.items) && data.items.length) {
        likesOptionsState.value = data.items
      }
    } catch (e) {
      console.warn('fetchLikesOptions fallback to default:', e)
      likesOptionsState.value = DEFAULT_LIKES_OPTIONS
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
  // 候補（computedとして公開）
  likesOptions: computed(() => likesOptionsState.value),
  selectedLikes,
  setSelectedLikes: (arr) => { selectedLikes.value = Array.isArray(arr) ? arr.slice(0, 10) : [] },
  fetchLikesOptions,
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
  saveUserHobbies,
  runProcessingFlow,
  }
})
;

