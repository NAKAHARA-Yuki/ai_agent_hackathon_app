'use client';

import React, { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useQuizStore } from '@/stores/quizStore';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, ChevronRight, Edit3 } from 'lucide-react';
import { appPath } from '@/utils/pathHelper';

export default function QuestionPage() {
  const router = useRouter();
  const params = useParams();
  const store = useQuizStore();

  const [questionNumber, setQuestionNumber] = useState(0);
  const [selectedOption, setSelectedOption] = useState<number | null>(null);
  const [freeText, setFreeText] = useState('');
  const [initialized, setInitialized] = useState(false);

  const numStr = params.questionNumber as string;

  // Initialize and load questions
  useEffect(() => {
    const init = async () => {
      if (store.questions.length === 0) {
        await store.fetchQuestions();
      }
      
      const num = parseInt(numStr, 10);
      if (!isNaN(num) && num > 0 && num <= store.questions.length) {
        setQuestionNumber(num);
        // Sync index
        store.currentQuestionIndex = num - 1;
        
        // Restore previous answer if exists
        const prev = store.userAnswers[store.questions[num - 1]?.id];
        if (prev) {
          setSelectedOption(prev.score);
          setFreeText(prev.freeText || '');
        } else {
          setSelectedOption(null);
          setFreeText('');
        }
      } else {
        router.replace(appPath('/'));
      }
      setInitialized(true);
    };
    init();
  }, [numStr, store.questions.length, router]);

  const currentQuestion = store.questions[questionNumber - 1];

  const handleNext = () => {
    if (selectedOption !== null && currentQuestion) {
      if (selectedOption === 0 && freeText.trim() === '') {
        alert('自由記述欄に回答を入力してください。');
        return;
      }

      store.recordAnswer(
        currentQuestion.id,
        selectedOption,
        freeText,
        currentQuestion.trait,
        currentQuestion.question
      );

      const nextIdx = store.nextQuestion();
      if (nextIdx !== null) {
        router.push(appPath(`/question/${nextIdx + 1}`));
      } else {
        // Go to Interests (likes selection)
        router.push(appPath('/interests'));
      }
    }
  };

  const handleBack = () => {
    if (questionNumber > 1) {
      router.push(appPath(`/question/${questionNumber - 1}`));
    } else {
      router.push(appPath('/'));
    }
  };

  if (!initialized || !currentQuestion) {
    return (
      <div className="flex-1 flex justify-center items-center">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  // Calculate progress percent
  const percent = ((questionNumber - 1) / store.questions.length) * 100;

  // Question options from API configuration:
  // If not customized, defaults to standard scale of: Very much (4), Mildly (3), Neutral (2), Mildly No (1), Custom text (0)
  // Let's check typical options
  const defaultOptions = [
    { score: 4, text: '非常にあてはまる' },
    { score: 3, text: 'ややあてはまる' },
    { score: 2, text: 'どちらともいえない' },
    { score: 1, text: 'あまりあてはまらない' },
    { score: 0, text: '自分で詳しく書く（自由記述）' },
  ];

  // In the DB, the question has 'options' or we fallback to default scale
  const optionsList = (currentQuestion as any).options || defaultOptions;
  const isFreeTextSelected = selectedOption === 0;

  return (
    <div className="flex-1 flex flex-col justify-between px-6 py-8 relative overflow-hidden">
      {/* Top navigation */}
      <div className="flex items-center gap-4">
        <button
          onClick={handleBack}
          className="p-2 rounded-xl border border-gray-200 bg-gray-50 hover:bg-gray-100 text-slate-600 hover:text-slate-800 transition-all cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1">
          {/* Progress bar container */}
          <div className="w-full bg-gray-100 border border-gray-200 h-2 rounded-full overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${percent}%` }}
              transition={{ duration: 0.3 }}
              className="h-full bg-blue-600 rounded-full"
            />
          </div>
        </div>
        <div className="text-[10px] font-bold text-slate-500 tracking-wider">
          {questionNumber} / {store.questions.length}
        </div>
      </div>

      {/* Main question card */}
      <div className="flex-1 flex flex-col justify-center my-6">
        <motion.div
          key={questionNumber}
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="space-y-6"
        >
          {/* Header */}
          <div className="text-center">
            <span className="text-[11px] font-bold tracking-wider text-blue-600 uppercase">
              Question {questionNumber}
            </span>
            <h2 className="text-lg font-bold text-slate-800 mt-1 leading-snug">
              {currentQuestion.question}
            </h2>
          </div>

          {/* Options */}
          <div className="space-y-3">
            {optionsList.map((opt: any) => {
              const isSelected = selectedOption === opt.score;
              return (
                <button
                  key={opt.score}
                  onClick={() => setSelectedOption(opt.score)}
                  className={`w-full text-left p-4 rounded-xl text-sm transition-all flex items-center justify-between border cursor-pointer ${
                    isSelected
                      ? 'border-blue-500 bg-blue-50 text-blue-700 font-semibold'
                      : 'border-gray-200 bg-white text-slate-600 hover:bg-gray-50 hover:border-gray-300'
                  }`}
                >
                  <span>{opt.text}</span>
                  {isSelected && (
                    <motion.div
                      layoutId="selectedIndicator"
                      className="w-2 h-2 rounded-full bg-blue-500 shadow-md shadow-blue-500/20"
                    />
                  )}
                </button>
              );
            })}
          </div>

          {/* Free Text Area */}
          <AnimatePresence>
            {isFreeTextSelected && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.3 }}
                className="overflow-hidden"
              >
                <div className="space-y-3 pt-2">
                  <label className="text-[11px] font-bold tracking-wider text-slate-500 flex items-center gap-1">
                    <Edit3 className="w-3 h-3 text-blue-600" />
                    {(currentQuestion as any).free_text_prompt || 'あなたの考えを教えてください：'}
                  </label>
                  <textarea
                    value={freeText}
                    onChange={(e) => setFreeText(e.target.value)}
                    rows={4}
                    placeholder={(currentQuestion as any).free_text_placeholder || 'ここに入力してください...'}
                    className="w-full p-4 glass-input text-slate-800 focus:outline-none text-xs leading-relaxed"
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </div>

      {/* Action Footer */}
      <div>
        <motion.button
          whileTap={{ scale: 0.98 }}
          onClick={handleNext}
          disabled={selectedOption === null}
          className={`w-full py-4 rounded-xl text-sm font-semibold text-white shadow-lg transition-all flex justify-center items-center gap-1 ${
            selectedOption === null
              ? 'bg-gray-200 text-gray-400 cursor-not-allowed border border-gray-200'
              : 'animated-gradient cursor-pointer'
          }`}
        >
          次へ <ChevronRight className="w-4 h-4" />
        </motion.button>
      </div>
    </div>
  );
}
