'use client';

import React, { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useAuthStore } from '@/stores/authStore';
import { planDetail, deletePlan, Plan } from '@/services/apiClient';
import { transportLabel, transportIcon, formatDuration, formatDistance } from '@/utils/transportHelpers';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, Trash2, Edit, Calendar, Clock, MapPin, AlertTriangle, ShieldAlert } from 'lucide-react';
import { appPath } from '@/utils/pathHelper';

export default function PlanDetailPage() {
  const router = useRouter();
  const params = useParams();
  const auth = useAuthStore();

  const [plan, setPlan] = useState<Plan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const planId = params.id as string;

  const loadPlan = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await planDetail(planId, auth.authHeader());
      setPlan(data);
    } catch (e: any) {
      if (e.message && e.message.includes('HTTP 503')) {
        setError('サーバーが混雑しています。時間をおいて再試行してください。');
      } else {
        setError('データの読み込みに失敗しました。');
      }
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!auth.isAuthenticated) {
      router.replace(appPath('/login'));
      return;
    }
    loadPlan();
  }, [planId, auth.isAuthenticated, router]);

  const handleDelete = async () => {
    if (deleting) return;
    setDeleting(true);
    try {
      await deletePlan(planId, auth.authHeader());
      router.replace(appPath('/plans'));
    } catch (e) {
      console.error(e);
      alert('プランの削除に失敗しました。');
      setDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

  const getPlanImage = (p: Plan) => {
    if (p.image_base64) {
      const mime = p.image_mime_type || 'image/png';
      return `data:${mime};base64,${p.image_base64}`;
    }
    if (p.image_url) return p.image_url;
    if (p.hero_image) return p.hero_image;
    
    // Fallback image
    const hash = p.title.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
    return `https://images.unsplash.com/photo-1488646953014-85cb44e25828?auto=format&fit=crop&w=600&q=80&sig=${hash % 100}`;
  };

  if (loading) {
    return (
      <div className="flex-1 flex justify-center items-center">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-indigo-500"></div>
      </div>
    );
  }

  if (error || !plan) {
    return (
      <div className="flex-1 flex flex-col justify-center items-center px-6 text-center space-y-4">
        <ShieldAlert className="w-8 h-8 text-rose-400" />
        <p className="text-slate-400 text-sm">{error || 'プランが見つかりませんでした。'}</p>
        <button
          onClick={() => router.push(appPath('/plans'))}
          className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 transition-all cursor-pointer"
        >
          プラン一覧へ戻る
        </button>
      </div>
    );
  }

  const bgImg = getPlanImage(plan);

  return (
    <div className="flex-1 flex flex-col justify-start relative overflow-y-auto max-h-screen">
      {/* Hero background image */}
      <div
        style={{ backgroundImage: `url(${bgImg})` }}
        className="h-48 bg-cover bg-center relative flex flex-col justify-between p-4"
      >
        <div className="absolute inset-0 bg-slate-950/40" />
        
        {/* Float back button */}
        <div className="relative flex justify-between items-center z-10">
          <button
            onClick={() => router.push(appPath('/plans'))}
            className="p-2 rounded-xl border border-white/10 bg-black/40 text-white transition-all cursor-pointer backdrop-blur-md"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
        </div>

        {/* Hero Title */}
        <div className="relative bg-slate-950/50 backdrop-blur-[2px] p-3 rounded-xl max-w-sm">
          <h1 className="text-base font-bold text-white leading-snug">{plan.title}</h1>
        </div>
      </div>

      {/* Main Details Body */}
      <div className="p-6 space-y-6 pb-24">
        {/* Brief/Summary */}
        {plan.text && (
          <div className="glass-panel rounded-2xl p-4 space-y-2">
            <h3 className="text-xs font-bold text-slate-300">💡 旅の概要</h3>
            <p className="text-xs text-slate-300 leading-relaxed font-outfit whitespace-pre-wrap">{plan.text}</p>
          </div>
        )}

        {/* Suggested keywords/tags */}
        {plan.suggestions && plan.suggestions.length > 0 && (
          <div className="glass-panel rounded-2xl p-4 space-y-3">
            <h3 className="text-xs font-bold text-slate-300">📌 おすすめの観光地候補</h3>
            <ul className="space-y-2">
              {plan.suggestions.map((s: any, idx: number) => (
                <li key={idx} className="text-xs border-b border-white/5 pb-2 last:border-b-0 last:pb-0">
                  <div className="font-semibold text-white">{s.title}</div>
                  {s.brief && <p className="text-[10px] text-slate-400 mt-0.5 leading-normal">{s.brief}</p>}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Itinerary Timeline */}
        {plan.itinerary && plan.itinerary.length > 0 && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-1.5">
              <Calendar className="w-4 h-4 text-indigo-400" />
              旅程タイムライン
            </h3>

            <div className="space-y-6 pl-4 border-l border-white/5 relative">
              {plan.itinerary.map((day: any, dIdx: number) => (
                <div key={dIdx} className="space-y-4 relative">
                  {/* Day marker node */}
                  <div className="absolute -left-[25px] top-1.5 w-4 h-4 rounded-full border border-indigo-500 bg-[#090b11] flex items-center justify-center text-[8px] font-bold text-indigo-400 shadow-md">
                    D{day.day}
                  </div>

                  <div className="font-bold text-xs text-white pl-2">Day {day.day}</div>
                  
                  <div className="space-y-3.5 pl-2">
                    {(day.items || []).map((item: any, iIdx: number) => (
                      <div key={iIdx} className="space-y-2">
                        {/* Event Card */}
                        <div className="bg-white/5 border border-white/5 rounded-xl p-3.5 space-y-1">
                          <div className="flex items-center gap-1.5 text-[9px] font-bold text-indigo-400">
                            <Clock className="w-3.5 h-3.5" /> {item.time || '時間指定なし'}
                          </div>
                          <h4 className="text-xs font-bold text-white leading-snug">{item.title}</h4>
                          {item.detail && (
                            <p className="text-[10px] text-slate-400 leading-relaxed mt-1">
                              {item.detail}
                            </p>
                          )}
                          {item.location && (
                            <span className="inline-flex items-center gap-0.5 text-[9px] text-slate-500 mt-1">
                              <MapPin className="w-3 h-3" /> {item.location}
                            </span>
                          )}
                        </div>

                        {/* Transport indicator *after* the activity card */}
                        {item.transport && (
                          <div className="flex items-center gap-1.5 pl-4 py-1 text-[9px] text-slate-500 font-mono">
                            <span className="text-xs">{transportIcon(item.transport.mode)}</span>
                            <span>{transportLabel(item.transport.mode)}</span>
                            {formatDuration(item.transport.estimated_duration) && (
                              <>
                                <span>•</span>
                                <span>{formatDuration(item.transport.estimated_duration)}</span>
                              </>
                            )}
                            {formatDistance(item.transport.distance_km) && (
                              <>
                                <span>•</span>
                                <span>{formatDistance(item.transport.distance_km)}</span>
                              </>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Place check marks */}
        {plan.places && plan.places.length > 0 && (
          <div className="glass-panel rounded-2xl p-4 space-y-3">
            <h3 className="text-xs font-bold text-slate-300">📍 主要目的地・スポット</h3>
            <div className="grid grid-cols-1 gap-2">
              {plan.places.map((place: any, pIdx: number) => (
                <div key={pIdx} className="bg-white/5 rounded-xl p-2.5 flex items-start gap-2">
                  <MapPin className="w-4 h-4 text-indigo-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <span className="text-xs font-semibold text-white block">{place.name}</span>
                    {place.note && (
                      <span className="text-[9px] text-slate-400 leading-normal block mt-0.5">
                        {place.note}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Sticky Action Footer */}
      <div className="border-t border-white/5 pt-4 bg-[#090b11]/85 backdrop-blur-md px-6 py-4 absolute bottom-0 left-0 right-0 z-40 flex gap-3">
        <button
          onClick={() => setShowDeleteConfirm(true)}
          className="flex-1 py-3.5 rounded-xl text-xs font-semibold text-rose-400 border border-rose-950 bg-rose-950/20 hover:bg-rose-950/40 transition-all flex items-center justify-center gap-1.5 cursor-pointer"
        >
          <Trash2 className="w-4 h-4" /> プランを削除
        </button>

        <button
          onClick={() => router.push(appPath(`/plans/${planId}/chat`))}
          className="flex-1 py-3.5 rounded-xl text-xs font-semibold text-white animated-gradient shadow-lg flex items-center justify-center gap-1.5 cursor-pointer"
        >
          <Edit className="w-4 h-4" /> ブラッシュアップ
        </button>
      </div>

      {/* Delete Confirmation Modal */}
      <AnimatePresence>
        {showDeleteConfirm && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setShowDeleteConfirm(false)}
            className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm z-50 flex items-center justify-center p-6"
          >
            <motion.div
              initial={{ scale: 0.95, y: 15 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 15 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-xs glass-panel rounded-2xl p-5 space-y-4 border border-rose-900/40 shadow-2xl text-center"
            >
              <div className="w-10 h-10 rounded-full bg-rose-500/10 border border-rose-500/20 flex items-center justify-center mx-auto text-rose-400">
                <AlertTriangle className="w-5 h-5 animate-bounce" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white">プランを削除しますか？</h3>
                <p className="text-[10px] text-slate-400 mt-2 leading-relaxed">
                  「{plan.title}」を完全に削除します。<br />この操作は取り消せません。
                </p>
              </div>
              <div className="flex gap-2.5 pt-2">
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  className="flex-1 py-2.5 rounded-xl text-xs font-semibold text-slate-300 border border-white/5 bg-white/5 hover:bg-white/10"
                >
                  キャンセル
                </button>
                <button
                  onClick={handleDelete}
                  disabled={deleting}
                  className="flex-1 py-2.5 rounded-xl text-xs font-semibold text-white bg-rose-600 hover:bg-rose-500 shadow-md"
                >
                  {deleting ? '削除中...' : '削除する'}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
