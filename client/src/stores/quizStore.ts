import { create } from 'zustand';

export interface QuestionScale {
  value: number;
  label: string;
}

export interface Question {
  id: string;
  question: string;
  trait: string;
  scale: QuestionScale[];
}

export interface Answer {
  score: number;
  freeText: string;
  trait: string;
  question: string;
}

export interface LikeOption {
  id: string;
  label: string;
  emoji: string;
  weights: Record<string, number>;
}

export interface QuizResult {
  title: string;
  description: string;
  plans: any[] | null;
  scoreDetails: {
    average: string;
    traitScores: Record<string, number>;
    answers: {
      question: string;
      finalScore: number;
      explanation: string;
    }[];
  };
}

interface QuizState {
  questions: Question[];
  userAnswers: Record<string, Answer>;
  currentQuestionIndex: number;
  analyzedScores: Record<string, { score: number; explanation: string }>;
  selectedLikes: string[];
  likesOptions: LikeOption[];
  isAnalyzing: boolean;
  aiPlans: any[] | null;
  isGeneratingPlans: boolean;
  isProcessing: boolean;
  isSavingProfile: boolean;
  processingStage: 'idle' | 'analyzing' | 'scoring' | 'parallel' | 'done' | 'error';
  
  fetchQuestions: () => Promise<void>;
  recordAnswer: (questionId: string, score: number, freeText: string, trait: string, question: string) => void;
  nextQuestion: () => number | null; // returns target index if valid, or null if complete/needs redirect
  resetQuiz: () => void;
  analyzeFreeTextAnswers: () => Promise<void>;
  generateAIPlans: () => Promise<void>;
  savePersonaAndProfile: (authHeader: Record<string, string>) => Promise<void>;
  submitAllQuizData: (authHeader: Record<string, string>) => Promise<void>;
  setSelectedLikes: (likes: string[]) => void;
  getFinalResult: () => QuizResult | null;
  getProcessingPercent: () => number;
}

const DEFAULT_LIKES_OPTIONS: LikeOption[] = [
  { id: 'onsen', label: '温泉・サウナ', emoji: '♨️', weights: { comfort: 0.6, pace: -0.2 } },
  { id: 'relax', label: 'リラックス・スパ', emoji: '🧖', weights: { comfort: 0.8, activity: -0.4, pace: -0.4 } },
  { id: 'art', label: 'アート・美術館', emoji: '🖼️', weights: { culture: 0.7, novelty: 0.1 } },
  { id: 'history', label: '歴史・世界遺産', emoji: '🏛️', weights: { culture: 0.8 } },
  { id: 'nature', label: '自然・絶景', emoji: '🏞️', weights: { nature: 0.8, activity: 0.2 } },
  { id: 'gourmet', label: 'グルメ・食べ歩き', emoji: '🍣', weights: { gourmet: 0.8, comfort: 0.1 } },
  { id: 'citywalk', label: 'まち歩き', emoji: '🚶', weights: { activity: 0.4, culture: 0.2 } },
  { id: 'adventure', label: 'アドベンチャー', emoji: '🧗', weights: { novelty: 0.6, risk: 0.4, activity: 0.6 } },
  { id: 'themepark', label: 'テーマパーク', emoji: '🎢', weights: { comfort: 0.2, pace: 0.2 } },
  { id: 'island', label: '離島ステイ', emoji: '🏝️', weights: { nature: 0.6, novelty: 0.3, comfort: 0.2 } },
  { id: 'snow', label: '雪・ウィンター', emoji: '❄️', weights: { activity: 0.4, risk: 0.2, comfort: -0.1 } },
  { id: 'festival', label: '祭り・イベント', emoji: '🎊', weights: { social: 0.6, culture: 0.2 } },
  { id: 'pilgrimage', label: '聖地巡礼（アニメ・ドラマ）', emoji: '🎬', weights: { culture: 0.5, novelty: 0.3, planning: 0.2 } },
  { id: 'cafe', label: 'カフェめぐり', emoji: '☕', weights: { gourmet: 0.6, comfort: 0.2, pace: -0.1 } },
  { id: 'coffee', label: 'コーヒー巡り', emoji: '☕', weights: { gourmet: 0.5, comfort: 0.2, pace: -0.1 } },
  { id: 'sweets', label: 'スイーツ巡り', emoji: '🍰', weights: { gourmet: 0.5, comfort: 0.2 } },
  { id: 'bakery', label: 'ベーカリー巡り', emoji: '🥖', weights: { gourmet: 0.4, comfort: 0.2, pace: -0.1 } },
  { id: 'sushi_love', label: '寿司巡り', emoji: '🍣', weights: { gourmet: 0.5 } },
  { id: 'wagashi', label: '和菓子', emoji: '🍡', weights: { gourmet: 0.4, culture: 0.2 } },
  { id: 'craftbeer', label: 'クラフトビール', emoji: '🍺', weights: { gourmet: 0.4, social: 0.3 } },
  { id: 'wine', label: 'ワイン', emoji: '🍷', weights: { gourmet: 0.4, comfort: 0.2 } },
  { id: 'sake', label: '日本酒', emoji: '🍶', weights: { gourmet: 0.4, culture: 0.2 } },
  { id: 'vegan', label: 'ヴィーガン対応', emoji: '🥦', weights: { gourmet: 0.2, planning: 0.2, comfort: 0.1 } },
  { id: 'shrines', label: '神社仏閣', emoji: '⛩️', weights: { culture: 0.6, pace: -0.1 } },
  { id: 'goshuin', label: '御朱印集め', emoji: '📖', weights: { culture: 0.5, planning: 0.2 } },
  { id: 'castles', label: '城めぐり', emoji: '🏯', weights: { culture: 0.6, activity: 0.2 } },
  { id: 'hanabi', label: '花火', emoji: '🎆', weights: { social: 0.3, culture: 0.2 } },
  { id: 'sakura', label: '桜', emoji: '🌸', weights: { nature: 0.4, culture: 0.2 } },
  { id: 'momiji', label: '紅葉', emoji: '🍁', weights: { nature: 0.5, activity: 0.1, pace: -0.1 } },
  { id: 'waterfalls', label: '滝めぐり', emoji: '🌊', weights: { nature: 0.6, activity: 0.3, risk: 0.1 } },
  { id: 'nightview', label: '夜景・イルミ', emoji: '🌃', weights: { culture: 0.2, novelty: 0.1, comfort: 0.1 } },
  { id: 'aquarium', label: '水族館', emoji: '🐠', weights: { culture: 0.2, comfort: 0.2 } },
  { id: 'zoo', label: '動物園・牧場', emoji: '🦁', weights: { nature: 0.3, social: 0.2 } },
  { id: 'kids', label: '子連れに優しい', emoji: '👨‍👩‍👧', weights: { comfort: 0.4, risk: 0.2, pace: -0.2 } },
  { id: 'pet', label: 'ペット同伴OK', emoji: '🐶', weights: { comfort: 0.2, planning: 0.2, nature: 0.2 } },
  { id: 'couple', label: 'カップル向け', emoji: '💑', weights: { comfort: 0.2, gourmet: 0.2, pace: -0.1 } },
  { id: 'girls', label: '女子旅', emoji: '👭', weights: { gourmet: 0.3, culture: 0.2 } },
  { id: 'solo', label: 'ひとり旅', emoji: '🧍', weights: { novelty: 0.2, planning: 0.1, comfort: -0.1 } },
  { id: 'photography', label: '写真撮影', emoji: '📸', weights: { nature: 0.3, culture: 0.2, planning: 0.1 } },
  { id: 'instaspot', label: '映えスポット', emoji: '✨', weights: { digital: 0.3, novelty: 0.2, culture: 0.1 } },
  { id: 'surf', label: 'サーフィン', emoji: '🏄', weights: { activity: 0.7, risk: 0.3, nature: 0.3 } },
  { id: 'sup', label: 'SUP・カヤック', emoji: '🛶', weights: { activity: 0.6, nature: 0.3 } },
  { id: 'snorkel', label: 'シュノーケリング', emoji: '🤿', weights: { activity: 0.6, nature: 0.4 } },
  { id: 'ski', label: 'スキー・スノボ', emoji: '🎿', weights: { activity: 0.7, risk: 0.3, nature: 0.3 } },
  { id: 'hike', label: 'ハイキング', emoji: '🥾', weights: { activity: 0.5, nature: 0.5 } },
  { id: 'climb', label: '登山', emoji: '⛰️', weights: { activity: 0.7, risk: 0.3, nature: 0.4 } },
  { id: 'trailrun', label: 'トレイルラン', emoji: '🏃‍♂️', weights: { activity: 0.7, risk: 0.2, nature: 0.3 } },
  { id: 'cycle', label: 'サイクリング', emoji: '🚴', weights: { activity: 0.5, nature: 0.3 } },
  { id: 'drive', label: 'ドライブ', emoji: '🚗', weights: { comfort: 0.2, activity: 0.2 } },
  { id: 'rail', label: '鉄道旅', emoji: '🚆', weights: { culture: 0.2, planning: 0.3, comfort: 0.1 } },
  { id: 'scenic_train', label: '絶景列車', emoji: '🚞', weights: { nature: 0.3, comfort: 0.2 } },
  { id: 'ferry', label: 'フェリー旅', emoji: '⛴️', weights: { comfort: 0.2, nature: 0.2 } },
  { id: 'cruise', label: 'クルーズ', emoji: '🚢', weights: { comfort: 0.6, pace: -0.2 } },
  { id: 'craft', label: '伝統工芸体験', emoji: '🎎', weights: { culture: 0.6, novelty: 0.2, activity: 0.1 } },
  { id: 'pottery', label: '陶芸体験', emoji: '🏺', weights: { culture: 0.5, activity: 0.2 } },
  { id: 'kintsugi', label: '金継ぎ', emoji: '🪡', weights: { culture: 0.5, planning: 0.2 } },
  { id: 'dyeing', label: '染物体験', emoji: '🧶', weights: { culture: 0.5 } },
  { id: 'sushi_making', label: '寿司握り体験', emoji: '🍣', weights: { gourmet: 0.4, culture: 0.3, activity: 0.1 } },
  { id: 'tea', label: '茶道・抹茶体験', emoji: '🍵', weights: { culture: 0.6, pace: -0.2 } },
  { id: 'kimono', label: '着物レンタル', emoji: '👘', weights: { culture: 0.5, digital: 0.1 } },
  { id: 'markets', label: '朝市・市場', emoji: '🧺', weights: { gourmet: 0.4, culture: 0.2, pace: 0.1 } },
  { id: 'outlet', label: 'アウトレット・ショッピング', emoji: '🛍️', weights: { budget: 0.3, comfort: 0.2 } },
  { id: 'thrift', label: '古着・蚤の市', emoji: '👗', weights: { budget: 0.2, novelty: 0.2, culture: 0.2 } },
  { id: 'tech', label: 'テック・ガジェット巡り', emoji: '📱', weights: { digital: 0.6, novelty: 0.2 } },
  { id: 'science_museum', label: '科学館・博物館', emoji: '🧪', weights: { culture: 0.5 } },
  { id: 'concept_cafe', label: 'コンセプトカフェ', emoji: '🧋', weights: { social: 0.2, culture: 0.2, novelty: 0.2 } },
  { id: 'yoga', label: 'ヨガ・ウェルネス', emoji: '🧘', weights: { comfort: 0.6, activity: 0.2, pace: -0.3 } },
];

function normalizeExplanation(raw: any): string {
  try {
    if (raw == null) return '';
    if (typeof raw === 'object') {
      if (typeof raw.explanation === 'string') return raw.explanation;
      if (typeof raw['解説'] === 'string') return raw['解説'];
      return JSON.stringify(raw);
    }
    const s = String(raw).trim();
    if ((s.startsWith('{') && s.endsWith('}')) || (s.startsWith('[') && s.endsWith(']'))) {
      try {
        const parsed = JSON.parse(s);
        if (parsed && typeof parsed === 'object') {
          if (typeof parsed.explanation === 'string') return parsed.explanation;
          if (typeof parsed['解説'] === 'string') return parsed['解説'];
          return JSON.stringify(parsed);
        }
      } catch (_) {}
    }
    if ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'"))) {
      return s.slice(1, -1);
    }
    return s;
  } catch (_) {
    return String(raw);
  }
}

// 簡易結果タイプ決定ロジック
function getResultType(score: number) {
  if (score >= 3.2) {
    return {
      title: 'フロンティア・アドベンチャラー',
      description: '刺激と挑戦を求め、未知なる地へ飛び込むスタイル。',
      plans: [{ title: '屋久島縄文杉トレッキング＆秘境めぐり' }, { title: '北海道・大自然アドベンチャーツアー' }]
    };
  } else if (score >= 2.5) {
    return {
      title: 'カルチャー・エクスプローラー',
      description: '旅先の歴史、アート、現地コミュニティと深く関わるスタイル。',
      plans: [{ title: '京都・奥嵯峨の歴史散策と伝統工芸体験' }, { title: '金沢・アートと美食をめぐる旅' }]
    };
  } else {
    return {
      title: 'コンフォート・リラクサー',
      description: 'ゆったりとしたペースで、上質な癒やしと安らぎを得るスタイル。',
      plans: [{ title: '箱根・隠れ宿の温泉三昧と美食プラン' }, { title: '沖縄・プライベートビーチでのウェルネスステイ' }]
    };
  }
}

export const useQuizStore = create<QuizState>((set, get) => ({
  questions: [],
  userAnswers: {},
  currentQuestionIndex: 0,
  analyzedScores: {},
  selectedLikes: [],
  likesOptions: DEFAULT_LIKES_OPTIONS,
  isAnalyzing: false,
  aiPlans: null,
  isGeneratingPlans: false,
  isProcessing: false,
  isSavingProfile: false,
  processingStage: 'idle',

  getProcessingPercent() {
    switch (get().processingStage) {
      case 'idle': return 0;
      case 'analyzing': return get().isAnalyzing ? 35 : 50;
      case 'scoring': return 65;
      case 'parallel': return (get().isGeneratingPlans || get().isSavingProfile) ? 85 : 95;
      case 'done': return 100;
      case 'error': return 100;
      default: return 0;
    }
  },

  async fetchQuestions() {
    try {
      const response = await fetch('/api/questions');
      if (!response.ok) throw new Error('Network response was not ok');
      const data = await response.json();
      set({ questions: data });
    } catch (error) {
      console.error('Failed to fetch questions:', error);
    }
  },

  recordAnswer(questionId, score, freeText, trait, question) {
    set((state) => ({
      userAnswers: {
        ...state.userAnswers,
        [questionId]: { score, freeText, trait, question }
      }
    }));
  },

  nextQuestion() {
    const idx = get().currentQuestionIndex;
    const total = get().questions.length;
    if (idx < total - 1) {
      set({ currentQuestionIndex: idx + 1 });
      return idx + 1;
    } else {
      set({ currentQuestionIndex: idx + 1 }); // 100%
      return null;
    }
  },

  resetQuiz() {
    set({
      userAnswers: {},
      currentQuestionIndex: 0,
      analyzedScores: {},
      aiPlans: null,
      selectedLikes: [],
      processingStage: 'idle',
    });
  },

  setSelectedLikes(likes) {
    set({ selectedLikes: likes });
  },

  async analyzeFreeTextAnswers() {
    set({ isAnalyzing: true, processingStage: 'analyzing' });
    const answersToAnalyze = Object.entries(get().userAnswers);
    
    const analysisPromises = answersToAnalyze.map(async ([questionId, answer]) => {
      try {
        const response = await fetch('/api/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: answer.freeText,
            trait: answer.trait,
            question: answer.question,
            base_score: answer.score,
            question_id: questionId
          }),
        });
        if (!response.ok) throw new Error('Network response was not ok');
        const result = await response.json();
        
        set((state) => ({
          analyzedScores: {
            ...state.analyzedScores,
            [questionId]: {
              score: result.analyzed_score,
              explanation: normalizeExplanation(result.explanation ?? result)
            }
          }
        }));
      } catch (error) {
        console.error(`Failed to analyze text for question ${questionId}:`, error);
        set((state) => ({
          analyzedScores: {
            ...state.analyzedScores,
            [questionId]: { score: answer.score, explanation: '分析中にエラーが発生しました。' }
          }
        }));
      }
    });

    await Promise.all(analysisPromises);
    set({ isAnalyzing: false });
  },

  getFinalResult() {
    const { questions, userAnswers, analyzedScores, selectedLikes, likesOptions, aiPlans } = get();
    if (Object.keys(userAnswers).length === 0 || questions.length === 0) return null;

    const answersWithFinalScores = questions.map((q) => {
      const userAnswer = userAnswers[q.id];
      const analyzedResult = analyzedScores[q.id];
      
      let finalScore = userAnswer?.score || 2.5;
      let explanation = '分析なし';

      if (analyzedResult) {
        if (userAnswer && typeof userAnswer.freeText === 'string' && userAnswer.freeText.trim() !== '') {
          finalScore = (userAnswer.score + analyzedResult.score) / 2;
          explanation = normalizeExplanation(analyzedResult.explanation);
        } else {
          finalScore = userAnswer.score;
          explanation = normalizeExplanation(analyzedResult.explanation);
        }
      } else if (userAnswer) {
        finalScore = userAnswer.score;
        explanation = 'この回答のAIによる追加分析はありません。';
      }
      
      return {
        question: q.question,
        finalScore,
        explanation
      };
    });

    const traitScores: Record<string, { total: number; count: number }> = {};
    questions.forEach((q) => {
      if (!traitScores[q.trait]) {
        traitScores[q.trait] = { total: 0, count: 0 };
      }
      const answer = answersWithFinalScores.find((a) => a.question === q.question);
      if (answer) {
        traitScores[q.trait].total += answer.finalScore;
        traitScores[q.trait].count++;
      }
    });

    let averagedTraitScores: Record<string, number> = {};
    Object.entries(traitScores).forEach(([trait, data]) => {
      averagedTraitScores[trait] = data.count > 0 ? data.total / data.count : 0;
    });

    if (Array.isArray(selectedLikes) && selectedLikes.length) {
      const clamp = (v: number) => Math.max(1, Math.min(4, v));
      const guessTag = (key: string) => {
        const k = String(key).toLowerCase();
        if (/(novel|新規|冒険|venture)/.test(k)) return 'novelty';
        if (/(pace|密度|ペース)/.test(k)) return 'pace';
        if (/(budget|予算|価格|コスト|value)/.test(k)) return 'budget';
        if (/(social|交流|社交|人)/.test(k)) return 'social';
        if (/(culture|文化|歴史|history|heritage)/.test(k)) return 'culture';
        if (/(nature|自然|景観)/.test(k)) return 'nature';
        if (/(gourmet|食|グルメ|food)/.test(k)) return 'gourmet';
        if (/(planning|計画|綿密)/.test(k)) return 'planning';
        if (/(comfort|快適|amenity|ラグジュ)/.test(k)) return 'comfort';
        if (/(activity|活動|エナジ|energy|アクティ)/.test(k)) return 'activity';
        if (/(risk|安全|セーフ)/.test(k)) return 'risk';
        if (/(digital|テクノ|デジ)/.test(k)) return 'digital';
        return null;
      };

      const weightsSumByTag: Record<string, number> = {};
      selectedLikes.forEach((id) => {
        const opt = likesOptions.find((o) => o.id === id);
        if (!opt) return;
        Object.entries(opt.weights || {}).forEach(([tag, w]) => {
          weightsSumByTag[tag] = (weightsSumByTag[tag] || 0) + w;
        });
      });

      Object.keys(averagedTraitScores).forEach((traitKey) => {
        const tag = guessTag(traitKey);
        if (!tag) return;
        const w = weightsSumByTag[tag];
        if (!w) return;
        averagedTraitScores[traitKey] = clamp(averagedTraitScores[traitKey] + w * 0.2);
      });
    }

    const overallAverage =
      Object.values(averagedTraitScores).reduce((sum, score) => sum + score, 0) /
      Object.keys(averagedTraitScores).length;

    const resultTypeDetails = getResultType(overallAverage);

    return {
      title: resultTypeDetails.title,
      description: resultTypeDetails.description,
      plans: aiPlans ?? resultTypeDetails.plans,
      scoreDetails: {
        average: overallAverage.toFixed(2),
        traitScores: averagedTraitScores,
        answers: answersWithFinalScores
      }
    };
  },

  async generateAIPlans() {
    const current = get().getFinalResult();
    if (!current) return;
    set({ isGeneratingPlans: true });
    try {
      const resp = await fetch('/api/generate_plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ travel_type: current.title, description: current.description })
      });
      if (!resp.ok) throw new Error('API failed');
      const data = await resp.json();
      set({ aiPlans: data.plans || [] });
    } catch (e) {
      console.error('Failed to generate AI plans:', e);
    } finally {
      set({ isGeneratingPlans: false });
    }
  },

  async savePersonaAndProfile(authHeader) {
    const current = get().getFinalResult();
    if (!current) return;
    set({ isSavingProfile: true });
    try {
      // 1. Save persona
      const personaPayload = {
        travel_type: current.title,
        scores: current.scoreDetails.traitScores,
        hobbies: get().selectedLikes
      };
      await fetch('/api/persona', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        body: JSON.stringify(personaPayload)
      });

      // 2. Update profile
      await fetch('/api/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        body: JSON.stringify({
          diagnosis_completed: true,
          travel_type: current.title
        })
      });
    } catch (e) {
      console.error('Failed to save profile/persona:', e);
      throw e;
    } finally {
      set({ isSavingProfile: false });
    }
  },

  async submitAllQuizData(authHeader) {
    set({ isProcessing: true, processingStage: 'analyzing' });
    try {
      // Step 1: AI analyze text answers
      await get().analyzeFreeTextAnswers();
      
      // Step 2: Scoring
      set({ processingStage: 'scoring' });
      await new Promise(r => setTimeout(r, 600));

      // Step 3: Run parallel API requests: AI plan generation & DB saving
      set({ processingStage: 'parallel' });
      await Promise.all([
        get().generateAIPlans(),
        get().savePersonaAndProfile(authHeader)
      ]);

      set({ processingStage: 'done' });
    } catch (error) {
      console.error('Submit quiz data failed:', error);
      set({ processingStage: 'error' });
      throw error;
    } finally {
      set({ isProcessing: false });
    }
  }
}));
