'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuthStore } from '@/stores/authStore';
import { useQuizStore } from '@/stores/quizStore';
import { motion, AnimatePresence } from 'framer-motion';
import { Compass, Sparkles, Activity, ShieldCheck, ArrowRight, UserPlus, LogIn } from 'lucide-react';
const stepsData = [
  {
    title: '1. 直感的に答えるだけ',
    desc: 'いくつかの簡単な質問に選択で回答。迷ったら自由記述であなたの好みを詳しく教えてください。',
    icon: <Compass className="w-12 h-12 text-blue-600" />,
  },
  {
    title: '2. あなたの旅タイプを分析',
    desc: 'AIが自由記述のニュアンスも精密に読み取り、あなたの10の特性別スコアを可視化します。',
    icon: <Activity className="w-12 h-12 text-blue-500" />,
  },
  {
    title: '3. AI旅行プランを自動生成',
    desc: '分析された旅行スタイルに基づき、あなた専用に最適化された国内旅行プランを即座に提案します。',
    icon: <Sparkles className="w-12 h-12 text-teal-600" />,
  },
];

export default function StartPage() {
  const router = useRouter();
  const auth = useAuthStore();
  const quiz = useQuizStore();

  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(true);

  useEffect(() => {
    // 認証チェックとリダイレクト
    const checkRedirect = async () => {
      if (auth.isAuthenticated) {
        try {
          const user = await auth.refreshMe();
          if (user?.diagnosis_completed) {
            router.replace('/main');
            return;
          }
        } catch {}
      }
      setCheckingAuth(false);
    };
    checkRedirect();
  }, [auth.isAuthenticated, router]);

  const handleStart = async () => {
    if (loading) return;
    setLoading(true);
    await quiz.fetchQuestions();
    
    if (quiz.questions.length > 0) {
      quiz.resetQuiz();
      router.push('/question/1');
    } else {
      alert('旅行スタイル診断の読み込みに失敗しました。時間をおいて再度お試しください。');
    }
    setLoading(false);
  };

  if (checkingAuth) {
    return (
      <div className="flex-1 flex justify-center items-center">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col justify-between px-6 py-12 relative overflow-hidden">
      {/* Background glowing decorations */}
      <div className="absolute top-1/6 left-1/10 w-80 h-80 bg-blue-600/10 rounded-full blur-3xl -z-10" />
      <div className="absolute bottom-1/6 right-1/10 w-96 h-96 bg-teal-500/10 rounded-full blur-3xl -z-10" />

      {/* Header Logged In User Status / Auth buttons */}
      <div className="flex justify-end items-center gap-3">
        {auth.isAuthenticated ? (
          <div className="text-xs text-slate-500 bg-gray-50 border border-gray-200 rounded-full px-3 py-1.5 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
            {auth.user?.name} さん
          </div>
        ) : (
          <div className="flex gap-2">
            <Link
              href="/login"
              className="text-xs font-semibold text-slate-600 hover:text-slate-800 px-3 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-100 transition-all flex items-center gap-1"
            >
              <LogIn className="w-3.5 h-3.5" /> ログイン
            </Link>
            <Link
              href="/signup"
              className="text-xs font-semibold text-white px-3 py-1.5 rounded-lg animated-gradient shadow-md flex items-center gap-1"
            >
              <UserPlus className="w-3.5 h-3.5" /> 登録
            </Link>
          </div>
        )}
      </div>

      {/* Hero section */}
      <div className="flex-1 flex flex-col justify-center items-center text-center my-8">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
          className="mb-8"
        >
          <div className="w-16 h-16 rounded-2xl animated-gradient flex items-center justify-center shadow-lg shadow-blue-500/20 mb-6 mx-auto">
            <Compass className="w-8 h-8 text-white animate-pulse" />
          </div>
          <h1 className="text-4xl font-extrabold tracking-tight text-slate-800 mb-4 font-outfit leading-tight">
            AI旅行スタイル診断
          </h1>
          <p className="text-sm text-slate-500 max-w-sm mx-auto leading-relaxed">
            わずか数分で、あなたに最適化された旅行スタイルを可視化。AIがオリジナルの国内旅行プランも自動生成します。
          </p>
        </motion.div>

        {/* Informational Sliders */}
        <div className="w-full glass-panel rounded-2xl p-6 shadow-xl min-h-[180px] flex flex-col justify-between mb-8">
          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.3 }}
              className="flex flex-col items-center text-center py-2"
            >
              <div className="mb-4">{stepsData[step].icon}</div>
              <h3 className="text-base font-bold text-slate-800 mb-2">
                {stepsData[step].title}
              </h3>
              <p className="text-xs text-slate-500 max-w-xs leading-relaxed">
                {stepsData[step].desc}
              </p>
            </motion.div>
          </AnimatePresence>

          {/* Stepper Dots */}
          <div className="flex justify-center gap-2 mt-4">
            {stepsData.map((_, i) => (
              <button
                key={i}
                onClick={() => setStep(i)}
                className={`h-1.5 rounded-full transition-all duration-300 ${
                  step === i ? 'w-5 bg-blue-600' : 'w-1.5 bg-slate-300'
                }`}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Action Footer */}
      <div className="space-y-4">
        {auth.isAuthenticated ? (
          <motion.button
            whileTap={{ scale: 0.98 }}
            onClick={handleStart}
            disabled={loading}
            className="w-full py-4 rounded-xl text-sm font-semibold text-white animated-gradient shadow-lg hover:shadow-blue-500/10 transition-all flex justify-center items-center gap-2 cursor-pointer"
          >
            {loading ? (
              <span className="animate-pulse">読み込み中...</span>
            ) : (
              <>
                診断を開始する <ArrowRight className="w-4 h-4" />
              </>
            )}
          </motion.button>
        ) : (
          <div className="space-y-3">
            <Link href="/login" className="block w-full">
              <motion.button
                whileTap={{ scale: 0.98 }}
                className="w-full py-4 rounded-xl text-sm font-semibold text-white animated-gradient shadow-lg transition-all flex justify-center items-center gap-2 cursor-pointer"
              >
                ログインして開始する <ArrowRight className="w-4 h-4" />
              </motion.button>
            </Link>
            <p className="text-[11px] text-center text-slate-500">
              診断データ保存および旅行プラン生成のため、アカウント登録が必要です。
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
