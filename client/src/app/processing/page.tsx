'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useQuizStore } from '@/stores/quizStore';
import { useAuthStore } from '@/stores/authStore';
import { motion, AnimatePresence } from 'framer-motion';
import { Compass, ShieldAlert } from 'lucide-react';

export default function ProcessingPage() {
  const router = useRouter();
  const quiz = useQuizStore();
  const auth = useAuthStore();

  const [error, setError] = useState('');

  useEffect(() => {
    const runFlow = async () => {
      try {
        const header = auth.authHeader();
        await quiz.submitAllQuizData(header);
        
        // Wait 1 second on success to let the user see the 100% stage
        setTimeout(() => {
          router.replace('/results');
        }, 1000);
      } catch (e: any) {
        console.error('Quiz processing failed:', e);
        setError(e?.message || '診断中に予期せぬエラーが発生しました。');
      }
    };
    runFlow();
  }, [auth.authHeader, quiz.submitAllQuizData, router]);

  // Stage text mapped from store status
  const getStageText = () => {
    switch (quiz.processingStage) {
      case 'analyzing':
        return 'AIがあなたの回答のニュアンスを深く読み取っています...';
      case 'scoring':
        return '回答スコアを計算し、好みに合わせて統合しています...';
      case 'parallel':
        return 'あなた専用の旅行プランを作成し、結果を保存しています...';
      case 'done':
        return '診断が完了しました！結果を表示します。';
      case 'error':
        return '一部の処理に失敗しましたが、結果を表示します。';
      default:
        return 'AI診断エンジンの初期化中...';
    }
  };

  const percent = quiz.getProcessingPercent();
  const stage = quiz.processingStage;

  return (
    <div className="flex-1 flex flex-col justify-center px-8 py-12 relative overflow-hidden">
      {/* Background glowing decorations */}
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-80 h-80 bg-blue-600/10 rounded-full blur-3xl -z-10" />

      <div className="w-full text-center space-y-8 max-w-sm mx-auto">
        {/* Animated Spin Compass Header */}
        <div className="relative w-20 h-20 mx-auto">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 4, ease: 'linear' }}
            className="w-full h-full rounded-full border border-dashed border-blue-500/30 flex items-center justify-center"
          >
            <Compass className="w-8 h-8 text-blue-600" />
          </motion.div>
          {/* Inner pulse */}
          <div className="absolute inset-2 bg-blue-50 rounded-full animate-ping -z-10" />
        </div>

        <div>
          <h1 className="text-xl font-bold text-slate-800 mb-2 font-outfit">
            AI診断中
          </h1>
          <p className="text-xs text-slate-500">
            あなたの価値観にマッチする最適な旅行プランを組み立てています。
          </p>
        </div>

        {/* Progress bar */}
        <div className="space-y-3">
          <div className="w-full bg-gray-100 border border-gray-200 h-2 rounded-full overflow-hidden">
            <motion.div
              animate={{ width: `${percent}%` }}
              transition={{ duration: 0.5 }}
              className="h-full bg-blue-600 rounded-full animated-gradient"
            />
          </div>
          <div className="flex justify-between items-center text-[10px] font-mono text-slate-500">
            <span>PROGRESS</span>
            <span>{percent}%</span>
          </div>
        </div>

        {/* Stage description text */}
        <div className="min-h-[40px] flex items-center justify-center">
          <AnimatePresence mode="wait">
            <motion.p
              key={stage}
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -5 }}
              className="text-xs font-medium text-blue-600 leading-relaxed max-w-xs"
            >
              {error ? (
                <span className="text-rose-600 flex items-center justify-center gap-1.5">
                  <ShieldAlert className="w-4 h-4" /> {error}
                </span>
              ) : (
                getStageText()
              )}
            </motion.p>
          </AnimatePresence>
        </div>

        {/* Steps List */}
        <div className="glass-panel rounded-2xl p-4 space-y-3 text-left">
          {[
            { id: 1, label: 'テキスト回答解析', active: stage === 'analyzing' || stage === 'scoring' || stage === 'parallel' || stage === 'done' },
            { id: 2, label: '診断スコア集計', active: stage === 'scoring' || stage === 'parallel' || stage === 'done' },
            { id: 3, label: 'プラン生成・保存', active: stage === 'parallel' || stage === 'done' },
          ].map((s) => (
            <div key={s.id} className="flex items-center gap-3">
              <div
                className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold border transition-colors ${
                  s.active
                    ? 'bg-blue-50 border-blue-500 text-blue-600'
                    : 'bg-gray-50 border-gray-200 text-slate-400'
                }`}
              >
                {s.id}
              </div>
              <span className={`text-xs transition-colors ${s.active ? 'text-slate-800 font-semibold' : 'text-slate-400'}`}>
                {s.label}
              </span>
            </div>
          ))}
        </div>

        {/* Error retry option */}
        {error && (
          <motion.button
            whileTap={{ scale: 0.98 }}
            onClick={() => router.replace('/results')}
            className="w-full py-3 rounded-xl text-xs font-semibold text-slate-600 border border-gray-200 hover:bg-gray-100 transition-all cursor-pointer"
          >
            処理を中断して結果へ進む
          </motion.button>
        )}
      </div>
    </div>
  );
}
