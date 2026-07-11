'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/authStore';
import { useActivePlanStore } from '@/stores/activePlanStore';
import { listPlans, Plan } from '@/services/apiClient';
import BottomNav from '@/components/BottomNav';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, MessageSquare, Calendar, Compass, ShieldAlert, Sparkles } from 'lucide-react';


export default function PlansPage() {
  const router = useRouter();
  const auth = useAuthStore();
  const activePlanStore = useActivePlanStore();

  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');

  const fetchPlansList = async () => {
    try {
      setError('');
      const j = await listPlans(auth.authHeader());
      const sorted = Array.isArray(j.items)
        ? j.items.sort((a, b) => ((b.created_at || '') > (a.created_at || '') ? 1 : -1))
        : [];
      setPlans(sorted);
      await activePlanStore.fetchActivePlan(auth.authHeader());
    } catch (e) {
      setError('読み込みに失敗しました。');
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!auth.isAuthenticated) {
      router.replace('/login');
      return;
    }
    fetchPlansList();
  }, [auth.isAuthenticated, router]);

  const showToast = (message: string) => {
    setToast(message);
    setTimeout(() => {
      setToast('');
    }, 2000);
  };

  const toggleActivePlan = async (e: React.MouseEvent, plan: Plan) => {
    e.stopPropagation(); // Card detail navigation skip
    try {
      const activeId = activePlanStore.activePlan?.id;
      if (activeId === plan.id) {
        await activePlanStore.deactivatePlan(auth.authHeader());
        showToast('旅行当日モードを無効化しました');
      } else {
        await activePlanStore.activatePlan(plan.id, auth.authHeader());
        showToast('旅行当日モードを有効化しました');
      }
    } catch (err: any) {
      showToast('エラーが発生しました: ' + (err.message || '不明なエラー'));
    }
  };

  const openTravelDayChat = () => {
    if (activePlanStore.activePlan) {
      router.push(`/travel-day/${activePlanStore.activePlan.id}`);
    }
  };

  const getPlanImage = (p: Plan) => {
    if (p.image_base64) {
      const mime = p.image_mime_type || 'image/png';
      return `data:${mime};base64,${p.image_base64}`;
    }
    if (p.image_url) return p.image_url;
    if (p.hero_image) return p.hero_image;
    
    // Stable stock photography fallback
    const hash = p.title.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
    return `https://images.unsplash.com/photo-1488646953014-85cb44e25828?auto=format&fit=crop&w=480&q=80&sig=${hash % 100}`;
  };

  const isCurrentActive = (id: string) => activePlanStore.activePlan?.id === id;

  return (
    <div className="flex-1 flex flex-col justify-between px-6 pt-8 relative overflow-hidden bg-white">
      {/* Background glowing decorations */}
      <div className="absolute top-1/4 right-1/10 w-72 h-72 bg-blue-600/5 rounded-full blur-3xl -z-10" />

      {/* Main Container */}
      <div className="flex-1 overflow-y-auto pr-1 pb-6 space-y-6 max-h-[85vh]">
        {/* Top Header */}
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.push('/main')}
            className="p-2 rounded-xl border border-gray-200 bg-gray-50 hover:bg-gray-100 text-slate-800 transition-all cursor-pointer"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h1 className="text-xl font-bold text-slate-800 font-outfit">保存したプラン</h1>
            <p className="text-[10px] text-slate-500">作成済みの全旅行プランを表示しています</p>
          </div>
        </div>

        {/* Active Plan Banner (Travel Day Mode) */}
        {activePlanStore.activePlan && (
          <motion.div
            initial={{ y: -10, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            className="rounded-2xl bg-gradient-to-r from-blue-600 to-blue-500 p-[1px] shadow-md shadow-blue-100"
          >
            <div className="bg-white rounded-2xl p-4 flex items-center justify-between">
              <div>
                <span className="text-[9px] font-bold text-blue-600 tracking-wider block mb-1">
                  TRAVEL DAY ACTIVE
                </span>
                <h3 className="text-xs font-bold text-slate-800 max-w-[180px] truncate">
                  {activePlanStore.activePlan.title}
                </h3>
              </div>
              <button
                onClick={openTravelDayChat}
                className="px-3 py-2 rounded-xl text-[10px] font-semibold text-white bg-blue-600 hover:bg-blue-500 flex items-center gap-1 cursor-pointer shadow-md"
              >
                <MessageSquare className="w-3.5 h-3.5" />
                当日チャットを開く
              </button>
            </div>
          </motion.div>
        )}

        {/* Loading & Error */}
        {loading ? (
          <div className="text-center py-12 text-xs text-slate-500">読み込み中...</div>
        ) : error ? (
          <div className="bg-rose-50 border border-rose-200 p-4 rounded-2xl flex items-center gap-3">
            <ShieldAlert className="w-5 h-5 text-rose-600 flex-shrink-0" />
            <span className="text-xs text-rose-700 font-medium">{error}</span>
          </div>
        ) : plans.length > 0 ? (
          <div className="space-y-4">
            {plans.map((p) => {
              const active = isCurrentActive(p.id);
              const bgImg = getPlanImage(p);
              const dateStr = p.created_at
                ? new Date(p.created_at).toLocaleDateString('ja-JP')
                : '';

              return (
                <div
                  key={p.id}
                  onClick={() => router.push(`/plans/${p.id}`)}
                  style={{ backgroundImage: `url(${bgImg})` }}
                  className={`relative rounded-2xl bg-cover bg-center overflow-hidden shadow-lg h-36 flex flex-col justify-between p-4 cursor-pointer border group transition-all duration-300 ${
                    active ? 'border-blue-500 scale-[1.01]' : 'border-gray-200'
                  }`}
                >
                  {/* Overlay background */}
                  <div className="absolute inset-0 bg-slate-950/60 group-hover:bg-slate-950/70 transition-colors -z-10" />

                  {/* Corner indicator / Active button */}
                  <div className="flex justify-between items-start">
                    {active ? (
                      <span className="bg-blue-600 text-white text-[9px] font-bold px-2 py-0.5 rounded-full flex items-center gap-0.5 shadow-md">
                        <Sparkles className="w-3 h-3 animate-pulse" /> 旅行当日
                      </span>
                    ) : (
                      <div />
                    )}

                    <button
                      onClick={(e) => toggleActivePlan(e, p)}
                      className={`p-2 rounded-xl border backdrop-blur-md transition-all cursor-pointer ${
                        active
                          ? 'border-blue-500 bg-blue-500/20 text-blue-300'
                          : 'border-white/10 bg-black/30 text-slate-400 hover:text-white hover:border-white/20'
                      }`}
                      title={active ? '当日モードを解除' : '当日モードを有効化'}
                    >
                      <MessageSquare className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  {/* Text details */}
                  <div className="space-y-1">
                    <h3 className="text-sm font-bold text-white max-w-[280px] truncate">
                      {p.title || '無題プラン'}
                    </h3>
                    <div className="flex items-center gap-3 text-[9px] text-slate-300 font-mono">
                      <span className="flex items-center gap-0.5">
                        <Calendar className="w-3.5 h-3.5" /> {dateStr}
                      </span>
                      <span>
                        {p.status === 'confirmed' ? '確定' : '下書き'}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="bg-white border border-gray-200 shadow-sm rounded-2xl py-16 px-6 text-center space-y-4">
            <Compass className="w-8 h-8 text-slate-400 mx-auto" />
            <div>
              <p className="text-xs text-slate-650">作成された旅行プランがありません。</p>
              <p className="text-[10px] text-slate-500 mt-1">最初のプランを作成して冒険に出かけましょう。</p>
            </div>
            <button
              onClick={() => router.push('/travel-wizard')}
              className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 transition-all shadow-md cursor-pointer"
            >
              旅行計画を作成する
            </button>
          </div>
        )}
      </div>

      {/* Floating toast message */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: 30, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 30, scale: 0.95 }}
            className="absolute bottom-20 left-1/2 -translate-x-1/2 bg-white border border-gray-200 px-4 py-2.5 rounded-xl text-xs font-medium text-slate-800 shadow-lg flex items-center gap-2 z-50 whitespace-nowrap"
          >
            <span className="w-1.5 h-1.5 bg-blue-600 rounded-full animate-ping" />
            {toast}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Bottom Navigation */}
      <BottomNav />
    </div>
  );
}
