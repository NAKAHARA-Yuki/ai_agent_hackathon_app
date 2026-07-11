'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/authStore';
import { useActivePlanStore } from '@/stores/activePlanStore';
import BottomNav from '@/components/BottomNav';
import { motion } from 'framer-motion';
import { MessageCircle, PlusCircle, Compass, Calendar, Clipboard, User, RefreshCw, AlertCircle } from 'lucide-react';
import { appPath } from '@/utils/pathHelper';

interface RecentPlan {
  id: string;
  title: string;
  summary: string;
  date: string;
  status: string;
}

export default function MainPage() {
  const router = useRouter();
  const auth = useAuthStore();
  const activePlanStore = useActivePlanStore();

  const [persona, setPersona] = useState<any>(null);
  const [recentPlans, setRecentPlans] = useState<RecentPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [plansLoading, setPlansLoading] = useState(true);
  const [error, setError] = useState('');

  const loadLatestPersona = async () => {
    try {
      setError('');
      const resp = await fetch('/api/persona/latest', {
        headers: { 'Content-Type': 'application/json', ...auth.authHeader() },
      });
      if (resp.ok) {
        const data = await resp.json();
        setPersona(data);
      } else {
        setPersona(null);
      }
    } catch (e: any) {
      console.error('Failed to load persona:', e);
      setError(e?.message || '読み込みに失敗しました');
      setPersona(null);
    } finally {
      setLoading(false);
    }
  };

  const loadRecentPlans = async () => {
    try {
      const resp = await fetch('/api/plans', {
        headers: { 'Content-Type': 'application/json', ...auth.authHeader() },
      });
      if (resp.ok) {
        const data = await resp.json();
        const formatted = (data.items || []).slice(0, 3).map((plan: any) => ({
          id: plan.id,
          title: plan.title,
          summary: plan.summary || plan.brief || '',
          date: plan.created_at
            ? new Date(plan.created_at).toLocaleDateString('ja-JP')
            : new Date().toLocaleDateString('ja-JP'),
          status: plan.status || 'confirmed',
        }));
        setRecentPlans(formatted);
      }
    } catch (e) {
      console.error('Failed to load recent plans:', e);
    } finally {
      setPlansLoading(false);
    }
  };

  useEffect(() => {
    if (!auth.isAuthenticated) {
      router.replace(appPath('/login'));
      return;
    }
    loadLatestPersona();
    loadRecentPlans();
    activePlanStore.fetchActivePlan(auth.authHeader());
  }, [auth.isAuthenticated, router]);

  const openTravelDayChat = () => {
    if (activePlanStore.activePlan) {
      router.push(appPath(`/travel-day/${activePlanStore.activePlan.id}`));
    }
  };

  if (loading && !persona) {
    return (
      <div className="flex-1 flex justify-center items-center">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col justify-between px-6 pt-8 relative overflow-hidden bg-white">
      {/* Background glowing decorations */}
      <div className="absolute top-1/4 left-1/10 w-72 h-72 bg-blue-600/5 rounded-full blur-3xl -z-10" />

      {/* Main dashboard content */}
      <div className="flex-1 overflow-y-auto pr-1 pb-6 space-y-6 max-h-[85vh]">
        {/* Top Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-xl font-bold text-slate-800 font-outfit">マイページ</h1>
            <p className="text-[10px] text-slate-500">旅行スタイルに基づきパーソナライズされています</p>
          </div>
          <button
            onClick={() => {
              setLoading(true);
              setPlansLoading(true);
              loadLatestPersona();
              loadRecentPlans();
            }}
            className="p-2 rounded-xl bg-gray-50 border border-gray-200 text-slate-500 hover:text-slate-800 hover:bg-gray-100 transition-all cursor-pointer"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {/* Active Plan Banner (Travel Day Mode) */}
        {activePlanStore.activePlan && (
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="rounded-2xl bg-gradient-to-r from-blue-600 to-blue-500 p-[1px] shadow-md shadow-blue-100"
          >
            <div className="bg-white rounded-2xl p-4 flex items-center justify-between">
              <div>
                <span className="text-[9px] font-bold text-blue-600 tracking-wider block mb-1">
                  TRAVEL DAY MODE ACTIVE
                </span>
                <h3 className="text-sm font-bold text-slate-800 max-w-[200px] truncate">
                  {activePlanStore.activePlan.title}
                </h3>
              </div>
              <button
                onClick={openTravelDayChat}
                className="px-3.5 py-2 rounded-xl text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 shadow-md flex items-center gap-1.5 cursor-pointer"
              >
                <MessageCircle className="w-4 h-4" />
                対話を開く
              </button>
            </div>
          </motion.div>
        )}

        {/* Error handling */}
        {error && (
          <div className="bg-rose-50 border border-rose-200 p-4 rounded-2xl flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />
            <div className="space-y-2">
              <p className="text-xs text-rose-700 font-medium">{error}</p>
              <button
                onClick={loadLatestPersona}
                className="px-3 py-1.5 rounded-lg text-[10px] font-semibold text-white bg-rose-600 hover:bg-rose-500"
              >
                再試行
              </button>
            </div>
          </div>
        )}

        {/* Persona Profile Card */}
        {persona?.profile ? (
          <div className="space-y-4">
            <div className="bg-white border border-gray-200 shadow-sm rounded-2xl p-5 shadow-md">
              <span className="text-[10px] font-bold text-blue-600 tracking-wider block mb-1">
                CURRENT STYLE
              </span>
              <h2 className="text-lg font-bold text-slate-800 mb-2">
                {persona.profile.title}
              </h2>
              <p className="text-xs text-slate-600 leading-relaxed">
                {persona.profile.description || '旅行のパーソナライズプロファイルです。'}
              </p>

              {/* Traits Breakdown */}
              {persona.profile.traitScores && Object.keys(persona.profile.traitScores).length > 0 && (
                <div className="mt-5 border-t border-gray-200 pt-4 space-y-3">
                  <h3 className="text-xs font-bold text-slate-700">📊 旅行特性サマリー</h3>
                  <div className="grid grid-cols-2 gap-2">
                    {Object.entries(persona.profile.traitScores).slice(0, 4).map(([trait, score]: any) => (
                      <div key={trait} className="bg-gray-50 border border-gray-200 rounded-xl p-2.5 space-y-1">
                        <div className="flex justify-between items-center text-[10px]">
                          <span className="text-slate-600 font-medium truncate max-w-[60px]">{trait}</span>
                          <span className="text-blue-600 font-bold font-mono">{score.toFixed(1)}</span>
                        </div>
                        <div className="w-full bg-gray-100 h-1 rounded-full overflow-hidden">
                          <div
                            style={{ width: `${(score / 4) * 100}%` }}
                            className="h-full bg-blue-600 rounded-full"
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="text-center pt-2">
                    <button
                      onClick={() => router.push(appPath('/results'))}
                      className="text-[10px] text-blue-600 hover:text-blue-700 transition-colors font-semibold"
                    >
                      詳細な診断グラフを表示する &rarr;
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="bg-white border border-gray-200 shadow-sm rounded-2xl p-6 text-center space-y-4">
            <User className="w-8 h-8 text-slate-400 mx-auto" />
            <div>
              <p className="text-xs text-slate-600">診断データが登録されていません。</p>
              <p className="text-[10px] text-slate-500 mt-1">旅行スタイルを分析してパーソナライズを開始しましょう。</p>
            </div>
            <button
              onClick={() => router.push(appPath('/'))}
              className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 transition-all shadow-md cursor-pointer"
            >
              スタイル診断を受ける
            </button>
          </div>
        )}

        {/* CTA Actions */}
        <div className="grid grid-cols-1 gap-3">
          <button
            onClick={() => router.push(appPath('/travel-wizard'))}
            className="w-full py-4 rounded-2xl font-semibold text-white bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-700 hover:to-blue-600 shadow-lg shadow-blue-100 flex items-center justify-center gap-2 cursor-pointer text-sm"
          >
            <PlusCircle className="w-5 h-5" /> 新しい旅行計画を作成
          </button>
        </div>

        {/* Recent Travel Plans */}
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <h3 className="text-sm font-bold text-slate-800 flex items-center gap-1.5">
              <Compass className="w-4 h-4 text-blue-600" />
              最近の旅行プラン
            </h3>
            <button
              onClick={() => router.push(appPath('/plans'))}
              className="text-[10px] text-blue-600 hover:text-blue-700 font-semibold"
            >
              すべて見る
            </button>
          </div>

          {plansLoading ? (
            <div className="text-center py-6 text-xs text-slate-500">読み込み中...</div>
          ) : recentPlans.length > 0 ? (
            <div className="space-y-2.5">
              {recentPlans.map((plan) => (
                <div
                  key={plan.id}
                  onClick={() => router.push(appPath(`/plans/${plan.id}`))}
                  className="bg-white border border-gray-200 hover:border-blue-300 hover:shadow-md transition-all shadow-sm rounded-2xl p-4 flex items-center justify-between cursor-pointer"
                >
                  <div className="space-y-1.5 max-w-[240px]">
                    <h4 className="text-xs font-bold text-slate-800 truncate">{plan.title}</h4>
                    <p className="text-[10px] text-slate-600 line-clamp-1 leading-normal">
                      {plan.summary || '旅程プランの詳細を表示します。'}
                    </p>
                    <div className="flex items-center gap-2 text-[9px] text-slate-500 font-mono">
                      <span className="flex items-center gap-0.5">
                        <Calendar className="w-3 h-3" /> {plan.date}
                      </span>
                      <span className="flex items-center gap-0.5">
                        <Clipboard className="w-3 h-3" />
                        {plan.status === 'confirmed' ? '確定' : '下書き'}
                      </span>
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-400" />
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-white border border-gray-200 shadow-sm rounded-2xl py-8 px-4 text-center text-xs text-slate-500">
              まだ保存されたプランはありません。
            </div>
          )}
        </div>
      </div>

      {/* Bottom Navigation */}
      <BottomNav />
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
