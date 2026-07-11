'use client';

import React, { useEffect, useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { useQuizStore, QuizResult } from '@/stores/quizStore';
import { useAuthStore } from '@/stores/authStore';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, CheckCircle2, ChevronDown, ChevronUp, MapPin, Sparkles, Navigation } from 'lucide-react';

import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
} from 'chart.js';
import { Radar } from 'react-chartjs-2';

ChartJS.register(
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend
);

// Fallback trait descriptions
const TRAIT_DESCRIPTIONS: Record<string, string> = {
  '新規性追求': '未知や型にはまらない体験をどれだけ求めるか（冒険型〜安定志向の連続）。',
  '旅程密度': '1日の予定をどれだけ詰め込むか（行動満載〜余白重視）。',
  '予算哲学': '価格・コスパ重視か、体験の質を優先するか。',
  '社会的志向性': '現地の人／他の旅行者との交流をどれだけ望むか。',
  '主な興味関心': '旅行の中心テーマ（例：グルメ、自然、文化・歴史、リラクゼーション）。',
  '計画志向性': '事前に緻密に計画するか、現地で柔軟に決めるか。',
  '快適性水準': '宿・移動における快適さ・アメニティの重視度。',
  '活動レベル': '旅行中の身体的アクティビティの強度。',
  '安全性の閾値': '治安・医療など安全面をどの程度重視するか。',
  'デジタル統合度': '計画から共有までテクノロジーをどれだけ活用するか。'
};

function sanitizeText(text: any): string {
  if (!text) return '';
  const cleaned = String(text).trim();
  if (/^[◯○〇\u25CB\u25CF\u25EF]+$/.test(cleaned)) {
    return '';
  }
  return cleaned;
}

export default function ResultsPage() {
  const router = useRouter();
  const quiz = useQuizStore();
  const auth = useAuthStore();

  const [showScoreDetails, setShowScoreDetails] = useState(false);
  const [personaData, setPersonaData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [initialized, setInitialized] = useState(false);

  // Load from store or API
  const shouldLoadFromAPI = useMemo(() => {
    const fresh = quiz.getFinalResult();
    return !fresh || !fresh.scoreDetails || isNaN(parseFloat(fresh.scoreDetails.average));
  }, [quiz]);

  useEffect(() => {
    const loadData = async () => {
      if (shouldLoadFromAPI) {
        try {
          setLoading(true);
          const resp = await fetch('/api/persona/latest', {
            headers: { 'Content-Type': 'application/json', ...auth.authHeader() },
          });
          if (resp.ok) {
            const data = await resp.json();
            setPersonaData(data);
          }
        } catch (e) {
          console.error('Failed to load persona:', e);
        } finally {
          setLoading(false);
        }
      }
      setInitialized(true);
    };
    loadData();
  }, [shouldLoadFromAPI, auth.authHeader]);

  // Combined result calculation
  const displayResult = useMemo<QuizResult | null>(() => {
    if (!shouldLoadFromAPI) {
      return quiz.getFinalResult();
    }

    if (!personaData?.profile) return null;
    const profile = personaData.profile;
    const traitScores = profile.traitScores || {};
    
    const scores = Object.values(traitScores).filter((s: any) => !isNaN(s)) as number[];
    const average = scores.length > 0 ? scores.reduce((sum, s) => sum + s, 0) / scores.length : 0;

    return {
      title: sanitizeText(profile.title) || '診断結果',
      description: sanitizeText(profile.description) || '診断結果の詳細情報を読み込み中です。',
      plans: personaData.plans || [],
      scoreDetails: {
        average: average.toFixed(2),
        traitScores: traitScores,
        answers: []
      }
    };
  }, [shouldLoadFromAPI, quiz, personaData]);

  if (!initialized || loading) {
    return (
      <div className="flex-1 flex justify-center items-center">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (!displayResult) {
    return (
      <div className="flex-1 flex flex-col justify-center items-center px-6 text-center space-y-4">
        <p className="text-slate-500 text-sm">有効な診断結果が見つかりませんでした。</p>
        <button
          onClick={() => router.push('/')}
          className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 transition-all cursor-pointer"
        >
          診断トップへ戻る
        </button>
      </div>
    );
  }

  // Chart data setup
  const chartLabels = Object.keys(displayResult.scoreDetails.traitScores);
  const chartDataValues = Object.values(displayResult.scoreDetails.traitScores);

  const radarData = {
    labels: chartLabels,
    datasets: [
      {
        label: 'あなたのスコア',
        data: chartDataValues,
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        borderColor: '#3b82f6',
        borderWidth: 2,
        pointBackgroundColor: '#3b82f6',
        pointBorderColor: '#fff',
        pointHoverBackgroundColor: '#fff',
        pointHoverBorderColor: '#3b82f6',
      },
    ],
  };

  const radarOptions = {
    scales: {
      r: {
        angleLines: {
          color: 'rgba(0, 0, 0, 0.08)',
        },
        grid: {
          color: 'rgba(0, 0, 0, 0.08)',
        },
        pointLabels: {
          color: '#475569',
          font: {
            size: 9,
            family: 'sans-serif',
          },
        },
        ticks: {
          color: '#64748b',
          backdropColor: 'transparent',
          font: {
            size: 8,
          },
          stepSize: 1,
        },
        min: 1,
        max: 4,
      },
    },
    plugins: {
      legend: {
        display: false,
      },
    },
  };

  const startPlan = (plan: any) => {
    // Generate temporary plan doc and active it
    // For simplicity, we direct to plans list or wizard
    router.push('/plans');
  };

  return (
    <div className="flex-1 flex flex-col justify-start px-6 py-8 relative overflow-y-auto max-h-screen bg-white">
      {/* Background glowing decorations */}
      <div className="absolute top-1/10 left-1/10 w-72 h-72 bg-blue-600/5 rounded-full blur-3xl -z-10" />
      <div className="absolute top-1/2 right-1/10 w-80 h-80 bg-teal-500/5 rounded-full blur-3xl -z-10" />

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <button
          onClick={() => router.push('/')}
          className="p-2 rounded-xl border border-gray-200 bg-gray-50 hover:bg-gray-100 text-slate-800 transition-all cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <span className="text-xs font-bold text-slate-500 tracking-wider font-outfit">
          DIAGNOSIS RESULT
        </span>
        <div className="w-8" />
      </div>

      <div className="space-y-6 pb-12">
        {/* Success badge */}
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="flex justify-center"
        >
          <div className="bg-emerald-50 border border-emerald-200 text-emerald-600 text-xs px-3 py-1 rounded-full flex items-center gap-1.5 font-bold">
            <CheckCircle2 className="w-4 h-4" /> 診断完了
          </div>
        </motion.div>

        {/* Title & Desc */}
        <div className="text-center">
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-800 mb-3 font-outfit">
            {displayResult.title}
          </h1>
          <p className="text-xs text-slate-600 leading-relaxed max-w-sm mx-auto bg-white border border-gray-200 shadow-sm p-4 rounded-xl">
            {displayResult.description}
          </p>
        </div>

        {/* Radar Chart */}
        <div className="bg-white border border-gray-200 shadow-sm rounded-2xl p-4 flex items-center justify-center min-h-[300px]">
          <div className="w-full max-w-[280px]">
            <Radar data={radarData} options={radarOptions} />
          </div>
        </div>

        {/* Trait breakdown toggles */}
        <div className="space-y-2">
          <button
            onClick={() => setShowScoreDetails(!showScoreDetails)}
            className="w-full py-3.5 px-4 rounded-xl bg-gray-50 border border-gray-200 text-slate-750 flex items-center justify-between text-xs font-semibold cursor-pointer hover:bg-gray-100"
          >
            <span>スコアリング詳細を確認する</span>
            {showScoreDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>

          <AnimatePresence>
            {showScoreDetails && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <div className="bg-white border border-gray-200 shadow-sm rounded-2xl p-4 space-y-4">
                  <div className="flex justify-between items-center border-b border-gray-200 pb-2 text-xs">
                    <span className="text-slate-500">総合平均スコア</span>
                    <span className="text-blue-600 font-bold text-sm font-mono">{displayResult.scoreDetails.average} / 4.00</span>
                  </div>

                  <div className="space-y-3">
                    {Object.entries(displayResult.scoreDetails.traitScores).map(([trait, score]) => (
                      <div key={trait} className="space-y-1.5">
                        <div className="flex justify-between text-xs">
                          <span className="text-slate-700 font-medium">{trait}</span>
                          <span className="text-slate-500 font-mono">{score.toFixed(2)}</span>
                        </div>
                        {/* Progress line */}
                        <div className="w-full bg-gray-100 h-1 rounded-full overflow-hidden">
                          <div
                            style={{ width: `${(score / 4) * 100}%` }}
                            className="h-full bg-blue-600 rounded-full"
                          />
                        </div>
                        {TRAIT_DESCRIPTIONS[trait] && (
                          <p className="text-[10px] text-slate-500 leading-normal">
                            {TRAIT_DESCRIPTIONS[trait]}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* AI Travel Plans */}
        {displayResult.plans && displayResult.plans.length > 0 && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-slate-800 flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-pink-500 animate-pulse" />
              AI生成のおすすめ旅行プラン
            </h3>

            <div className="space-y-3">
              {displayResult.plans.map((p: any, i: number) => (
                <div key={i} className="bg-white border border-gray-200 hover:border-blue-300 hover:shadow-md transition-all shadow-sm rounded-2xl p-4 flex flex-col justify-between min-h-[120px]">
                  <div>
                    <div className="text-xs text-blue-600 font-bold mb-1 flex items-center gap-1">
                      <MapPin className="w-3.5 h-3.5" /> Plan {i + 1}
                    </div>
                    <h4 className="text-sm font-bold text-slate-800 mb-2">{p.title || p.name}</h4>
                    <p className="text-[11px] text-slate-600 leading-relaxed">
                      {p.description || 'あなた専用のカスタマイズ旅程が準備されています。'}
                    </p>
                  </div>

                  <div className="flex justify-end mt-4">
                    <button
                      onClick={() => startPlan(p)}
                      className="px-3 py-1.5 rounded-lg text-[10px] font-semibold text-white bg-blue-600 hover:bg-blue-500 transition-all flex items-center gap-1 cursor-pointer"
                    >
                      <Navigation className="w-3 h-3" /> このプランを開始する
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Home redirect */}
        <div className="pt-4">
          <button
            onClick={() => router.push('/main')}
            className="w-full py-4 rounded-xl text-sm font-semibold text-white bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-700 hover:to-blue-600 shadow-md flex justify-center items-center gap-1 cursor-pointer"
          >
            ダッシュボードへ進む <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

function ChevronRight(props: any) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="lucide lucide-chevron-right w-4 h-4"
    >
      <path d="m9 18 6-6-6-6" />
    </svg>
  );
}
