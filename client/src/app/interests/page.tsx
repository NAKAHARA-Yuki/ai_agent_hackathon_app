'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useQuizStore } from '@/stores/quizStore';
import { useAuthStore } from '@/stores/authStore';
import { motion } from 'framer-motion';
import { ArrowLeft, Check, Compass } from 'lucide-react';
import { appPath } from '@/utils/pathHelper';

const MIN_REQUIRED = 3;

export default function InterestsPage() {
  const router = useRouter();
  const quiz = useQuizStore();
  const auth = useAuthStore();

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    // Restore previous choices if exist
    if (Array.isArray(quiz.selectedLikes)) {
      setSelected(new Set(quiz.selectedLikes));
    }
    setInitialized(true);
  }, [quiz.selectedLikes]);

  const toggleOption = (id: string) => {
    const newSelected = new Set(selected);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelected(newSelected);
  };

  const handleNext = () => {
    if (selected.size < MIN_REQUIRED) return;
    
    // Save selected likes to store
    quiz.setSelectedLikes(Array.from(selected));
    
    // Redirect to processing view
    router.push(appPath('/processing'));
  };

  const handleBack = () => {
    // Back to last question
    if (quiz.questions.length > 0) {
      router.push(appPath(`/question/${quiz.questions.length}`));
    } else {
      router.push(appPath('/'));
    }
  };

  if (!initialized) {
    return (
      <div className="flex-1 flex justify-center items-center">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-indigo-500"></div>
      </div>
    );
  }

  const canNext = selected.size >= MIN_REQUIRED;

  return (
    <div className="flex-1 flex flex-col justify-between px-6 py-8 relative overflow-hidden">
      {/* Top navigation */}
      <div className="flex items-center justify-between">
        <button
          onClick={handleBack}
          className="p-2 rounded-xl border border-white/5 bg-white/5 hover:bg-white/10 text-white transition-all cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <span className="text-xs font-bold text-slate-500 tracking-wider font-outfit">
          INTERESTS
        </span>
        <div className="w-8" /> {/* Spacer to align title */}
      </div>

      {/* Main content header */}
      <div className="my-6">
        <div className="text-center mb-6">
          <h1 className="text-xl font-bold text-white mb-2 font-outfit">
            好きなことを教えてください
          </h1>
          <p className="text-xs text-slate-400">
            あなたの好みに合う旅行プランを調整します。直感的に最低{MIN_REQUIRED}個以上選択してください。
          </p>
        </div>

        {/* Tiles Grid with native mobile scroll */}
        <div className="grid grid-cols-2 gap-3 max-h-[50vh] overflow-y-auto pr-1 pb-4">
          {quiz.likesOptions.map((opt) => {
            const isActive = selected.has(opt.id);
            return (
              <button
                key={opt.id}
                onClick={() => toggleOption(opt.id)}
                className={`flex flex-col items-center justify-center p-4 rounded-2xl border text-center transition-all cursor-pointer select-none min-h-[96px] ${
                  isActive
                    ? 'border-indigo-500 bg-indigo-950/20 text-white font-semibold shadow-md shadow-indigo-500/5'
                    : 'border-white/5 bg-white/5 text-slate-300 hover:bg-white/10'
                }`}
              >
                <span className="text-2xl mb-2" role="img" aria-label={opt.label}>
                  {opt.emoji}
                </span>
                <span className="text-xs leading-snug break-words">
                  {opt.label}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Action Footer (Sticky) */}
      <div className="border-t border-white/5 pt-4 bg-[#090b11]/80 backdrop-blur-md -mx-6 px-6">
        <div className="flex items-center justify-between mb-4">
          <div className="text-xs text-slate-400">
            選択数:{' '}
            <span className={canNext ? 'text-indigo-400 font-bold' : 'text-slate-500'}>
              {selected.size}
            </span>{' '}
            / {MIN_REQUIRED} 以上
          </div>
          {canNext && (
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              className="text-[10px] bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded-full flex items-center gap-1 font-bold"
            >
              <Check className="w-3 h-3" /> 条件クリア
            </motion.div>
          )}
        </div>

        <motion.button
          whileTap={{ scale: 0.98 }}
          onClick={handleNext}
          disabled={!canNext}
          className={`w-full py-4 rounded-xl text-sm font-semibold text-white shadow-lg transition-all flex justify-center items-center gap-1 ${
            !canNext
              ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-white/5'
              : 'animated-gradient cursor-pointer'
          }`}
        >
          次へ <ChevronRight className="w-4 h-4" />
        </motion.button>
      </div>
    </div>
  );
}

// ChevronRight helper as Lucide icon was not imported
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
