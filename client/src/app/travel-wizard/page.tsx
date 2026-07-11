'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/authStore';
import { createPlan, generatePlanImage } from '@/services/apiClient';
import { appPath } from '@/utils/pathHelper';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, Send, Sparkles, MapPin, Calendar, Clock, ChevronRight, CheckCircle2, MessageSquare, Save } from 'lucide-react';

type WizardView = 'input' | 'loading' | 'suggestions' | 'detail';

interface WizardPlan {
  id: number;
  category_label: string | null;
  title: string;
  tags: string;
  brief: string;
  itinerary: any[];
  places: any[];
  route_info: any;
  text: string;
  image_base64: string | null;
  image_mime_type: string | null;
  __raw?: any;
  __full?: any;
}

export default function TravelWizardPage() {
  const router = useRouter();
  const auth = useAuthStore();

  const [currentView, setCurrentView] = useState<WizardView>('input');
  const [keyword, setKeyword] = useState('');
  const [travelPlans, setTravelPlans] = useState<WizardPlan[]>([]);
  const [selectedPlan, setSelectedPlan] = useState<WizardPlan | null>(null);
  const [loadingTitle, setLoadingTitle] = useState('AIが旅行プランを生成中...');
  const [loadingSubtitle, setLoadingSubtitle] = useState('最適なプランを考えています。少しお待ちください。');
  const [saving, setSaving] = useState(false);

  // Concurrency helper for image generation
  const runWithConcurrency = async (taskFns: (() => Promise<void>)[], limit = 3) => {
    const total = taskFns.length;
    if (total === 0) return;
    const pool = Math.min(limit, total);
    let idx = 0;
    const runners = Array.from({ length: pool }, async () => {
      while (true) {
        const current = idx++;
        if (current >= total) break;
        await taskFns[current]();
      }
    });
    await Promise.all(runners);
  };

  const handleCreatePlan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!keyword.trim() || currentView !== 'input') return;

    setCurrentView('loading');
    setLoadingTitle('旅行プランを作成中...');
    setLoadingSubtitle('AIが最適な旅程を考えています。少しお待ちください。');

    try {
      const resp = await fetch('/api/agent/generate_plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...auth.authHeader() },
        body: JSON.stringify({ keyword: String(keyword) }),
      });

      if (!resp.ok) throw new Error('Failed to generate plans');
      const data = await resp.json();
      const plans = Array.isArray(data?.plans) ? data.plans.slice(0, 3) : [];
      
      setLoadingTitle('イメージ画像を生成中...');
      
      const enriched: WizardPlan[] = plans.map((p: any, i: number) => {
        const tagsStr = Array.isArray(p?.tags)
          ? p.tags.map((t: any) => String(t)).join('・')
          : typeof p?.tags === 'string'
          ? p.tags
          : '';
        return {
          id: i + 1,
          category_label: typeof p?.category_label === 'string' ? p.category_label : null,
          title: p?.title || `プラン ${i + 1}`,
          tags: tagsStr,
          brief: typeof p?.brief === 'string' ? p.brief : typeof p?.description === 'string' ? p.description : '',
          itinerary: Array.isArray(p?.itinerary) ? p.itinerary : [],
          places: Array.isArray(p?.places) ? p.places : [],
          route_info: p?.route_info ?? null,
          text: typeof p?.text === 'string' ? p.text : typeof p?.brief === 'string' ? p.brief : '',
          image_base64: null,
          image_mime_type: null,
          __raw: { ...p, category_label: typeof p?.category_label === 'string' ? p.category_label : null },
          __full: data,
        };
      });

      let done = 0;
      const total = enriched.length;
      setLoadingSubtitle(total ? `画像生成中... ${done}/${total}` : '画像生成の対象がありません');

      const taskFns = enriched.map((ep, i) => async () => {
        try {
          const source = plans[i] || {};
          const img = await generatePlanImage({
            plan: {
              title: source.title || `プラン ${i + 1}`,
              summary: data?.summary || source.brief || source.description || '',
              places: Array.isArray(source.places) ? source.places : [],
              itinerary: Array.isArray(source.itinerary) ? source.itinerary : [],
              route_info: source?.route_info ?? null,
            },
            authHeader: auth.authHeader(),
          });
          if (img && img.image_base64) {
            ep.image_base64 = img.image_base64;
            ep.image_mime_type = img.image_mime_type || 'image/png';
          }
        } catch (e) {
          // Ignore failures
        } finally {
          done++;
          setLoadingSubtitle(`画像生成中... ${done}/${total}`);
        }
      });

      await runWithConcurrency(taskFns, 3);
      setTravelPlans(
        enriched.length
          ? enriched
          : [
              {
                id: 1,
                category_label: null,
                title: '旅行プラン',
                tags: '',
                brief: 'プランを生成できませんでした。',
                itinerary: [],
                places: [],
                route_info: null,
                text: '生成エラー',
                image_base64: null,
                image_mime_type: null,
                __full: data,
              },
            ]
      );
      setCurrentView('suggestions');
    } catch (e) {
      console.error('Wizard agent error:', e);
      alert('旅行プランの生成中にエラーが発生しました。時間をおいて再試行してください。');
      setCurrentView('input');
    }
  };

  const handleSelectPlan = (p: WizardPlan) => {
    setSelectedPlan(p);
    setCurrentView('detail');
  };

  const handleSavePlan = async () => {
    if (!selectedPlan || saving) return;
    setSaving(true);
    try {
      const payload = {
        title: selectedPlan.title,
        text: selectedPlan.text || selectedPlan.tags || '',
        places: selectedPlan.places || [],
        route_info: selectedPlan.route_info || null,
        itinerary: selectedPlan.itinerary || [],
        image_base64: selectedPlan.image_base64,
        image_mime_type: selectedPlan.image_mime_type,
        status: 'draft', // Saved as draft first
      };

      const doc = await createPlan(payload, auth.authHeader());
      if (doc && doc.id) {
        router.push(appPath(`/plans/${doc.id}`));
      } else {
        throw new Error('Save returned invalid document');
      }
    } catch (e) {
      console.error('Failed to save plan:', e);
      alert('プランの保存に失敗しました。');
    } finally {
      setSaving(false);
    }
  };

  const handleRefine = async () => {
    if (!selectedPlan || saving) return;
    setSaving(true);
    try {
      // Save plan first, then redirect to chat refinement
      const payload = {
        title: selectedPlan.title,
        text: selectedPlan.text || selectedPlan.tags || '',
        places: selectedPlan.places || [],
        route_info: selectedPlan.route_info || null,
        itinerary: selectedPlan.itinerary || [],
        image_base64: selectedPlan.image_base64,
        image_mime_type: selectedPlan.image_mime_type,
        status: 'draft',
      };
      const doc = await createPlan(payload, auth.authHeader());
      if (doc && doc.id) {
        router.push(appPath(`/plans/${doc.id}/chat`));
      }
    } catch (e) {
      console.error('Failed to save before refine:', e);
      alert('対話の開始に失敗しました。');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col justify-start px-6 py-8 relative overflow-y-auto max-h-screen">
      {/* Top Background glowing decorations */}
      <div className="absolute top-1/4 right-1/10 w-72 h-72 bg-indigo-600/5 rounded-full blur-3xl -z-10" />

      {/* INPUT SCREEN */}
      {currentView === 'input' && (
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-8 my-auto"
        >
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push(appPath('/main'))}
              className="p-2 rounded-xl border border-white/5 bg-white/5 hover:bg-white/10 text-white transition-all cursor-pointer"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <div>
              <h1 className="text-xl font-bold text-white font-outfit">プラン作成</h1>
              <p className="text-[10px] text-slate-400">AIがオリジナルの旅程を設計します</p>
            </div>
          </div>

          <div className="glass-panel rounded-2xl p-6 shadow-xl space-y-6">
            <div className="text-center space-y-2">
              <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mx-auto text-indigo-400">
                <Sparkles className="w-6 h-6 animate-pulse" />
              </div>
              <h2 className="text-base font-bold text-white">どんな旅行がしたいですか？</h2>
              <p className="text-[11px] text-slate-400">
                目的地、日数、テーマなどを自由に入力してください。
              </p>
            </div>

            <form onSubmit={handleCreatePlan} className="space-y-4">
              <textarea
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                rows={4}
                placeholder="例: 京都の隠れた紅葉スポットを巡る2泊3日の大人旅。温泉と美味しい和食も楽しみたいです。"
                required
                className="w-full p-4 glass-input text-white focus:outline-none text-xs leading-relaxed"
              />

              <motion.button
                whileTap={{ scale: 0.98 }}
                type="submit"
                className="w-full py-4 rounded-xl text-sm font-semibold text-white animated-gradient shadow-lg flex justify-center items-center gap-1.5 cursor-pointer"
              >
                旅行計画を提案する <Send className="w-4 h-4" />
              </motion.button>
            </form>
          </div>
        </motion.div>
      )}

      {/* LOADING SCREEN */}
      {currentView === 'loading' && (
        <div className="flex-1 flex flex-col justify-center items-center text-center space-y-6 my-auto">
          <div className="relative w-16 h-16">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ repeat: Infinity, duration: 3, ease: 'linear' }}
              className="w-full h-full rounded-full border border-dashed border-indigo-500/30 flex items-center justify-center"
            >
              <Sparkles className="w-6 h-6 text-indigo-400 animate-pulse" />
            </motion.div>
            <div className="absolute inset-1.5 bg-indigo-500/5 rounded-full animate-ping -z-10" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white mb-2">{loadingTitle}</h2>
            <p className="text-xs text-slate-400 max-w-xs leading-relaxed">{loadingSubtitle}</p>
          </div>
        </div>
      )}

      {/* SUGGESTIONS SCREEN */}
      {currentView === 'suggestions' && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="space-y-6"
        >
          <div className="flex items-center justify-between">
            <button
              onClick={() => setCurrentView('input')}
              className="p-2 rounded-xl border border-white/5 bg-white/5 hover:bg-white/10 text-white transition-all cursor-pointer"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <span className="text-xs font-bold text-slate-500 tracking-wider font-outfit">
              SUGGESTIONS
            </span>
            <div className="w-8" />
          </div>

          <div className="text-center">
            <h2 className="text-base font-bold text-white mb-1">AIが3つのプランを提案しました</h2>
            <p className="text-[10px] text-slate-400">ご希望に一番近いプランを1つ選択してください。</p>
          </div>

          <div className="space-y-4">
            {travelPlans.map((plan) => {
              const imgUrl = plan.image_base64
                ? `data:${plan.image_mime_type || 'image/png'};base64,${plan.image_base64}`
                : 'https://images.unsplash.com/photo-1488646953014-85cb44e25828?auto=format&fit=crop&w=480&q=80';

              return (
                <div
                  key={plan.id}
                  onClick={() => handleSelectPlan(plan)}
                  className="glass-panel-interactive rounded-2xl overflow-hidden cursor-pointer shadow-lg flex flex-col justify-between"
                >
                  <div
                    style={{ backgroundImage: `url(${imgUrl})` }}
                    className="h-28 bg-cover bg-center relative"
                  >
                    <div className="absolute inset-0 bg-slate-950/40" />
                    {plan.category_label && (
                      <span className="absolute top-3 left-3 bg-indigo-500 text-white text-[9px] font-bold px-2 py-0.5 rounded-full">
                        {plan.category_label}
                      </span>
                    )}
                  </div>
                  <div className="p-4 space-y-2">
                    <h3 className="text-sm font-bold text-white">{plan.title}</h3>
                    {plan.tags && (
                      <p className="text-[10px] text-indigo-400 font-semibold">{plan.tags}</p>
                    )}
                    <p className="text-[11px] text-slate-400 leading-normal line-clamp-2">
                      {plan.brief}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </motion.div>
      )}

      {/* DETAIL SCREEN */}
      {currentView === 'detail' && selectedPlan && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="space-y-6"
        >
          <div className="flex items-center justify-between">
            <button
              onClick={() => setCurrentView('suggestions')}
              className="p-2 rounded-xl border border-white/5 bg-white/5 hover:bg-white/10 text-white transition-all cursor-pointer"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <span className="text-xs font-bold text-slate-500 tracking-wider font-outfit">
              PLAN DETAIL
            </span>
            <div className="w-8" />
          </div>

          {/* Banner image */}
          <div
            style={{
              backgroundImage: `url(${
                selectedPlan.image_base64
                  ? `data:${selectedPlan.image_mime_type || 'image/png'};base64,${selectedPlan.image_base64}`
                  : 'https://images.unsplash.com/photo-1488646953014-85cb44e25828?auto=format&fit=crop&w=480&q=80'
              })`,
            }}
            className="h-36 bg-cover bg-center rounded-2xl overflow-hidden relative shadow-lg flex flex-col justify-end p-4 border border-white/5"
          >
            <div className="absolute inset-0 bg-slate-950/50" />
            <div className="relative space-y-1">
              <h2 className="text-base font-bold text-white leading-snug">{selectedPlan.title}</h2>
              {selectedPlan.tags && (
                <p className="text-[10px] text-indigo-400 font-semibold">{selectedPlan.tags}</p>
              )}
            </div>
          </div>

          {/* Overview text */}
          <div className="glass-panel rounded-2xl p-4 space-y-2">
            <h3 className="text-xs font-bold text-slate-300">💡 旅の概要</h3>
            <p className="text-xs text-slate-400 leading-relaxed">{selectedPlan.brief || selectedPlan.text}</p>
          </div>

          {/* Itinerary vertical timeline */}
          {selectedPlan.itinerary && selectedPlan.itinerary.length > 0 && (
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-white flex items-center gap-1.5">
                <Calendar className="w-4 h-4 text-indigo-400" /> 旅程タイムライン
              </h3>

              <div className="space-y-6 pl-4 border-l border-white/5 relative">
                {selectedPlan.itinerary.map((day: any, dIdx: number) => (
                  <div key={dIdx} className="space-y-4 relative">
                    {/* Day circle node */}
                    <div className="absolute -left-[25px] top-1.5 w-4 h-4 rounded-full border border-indigo-500 bg-[#090b11] flex items-center justify-center text-[8px] font-bold text-indigo-400 shadow-md">
                      D{day.day}
                    </div>

                    <div className="font-bold text-xs text-white pl-2">Day {day.day}</div>
                    
                    <div className="space-y-3 pl-2">
                      {(day.activities || []).map((act: any, aIdx: number) => (
                        <div key={aIdx} className="bg-white/5 border border-white/5 rounded-xl p-3.5 space-y-1.5">
                          <div className="flex items-center gap-1.5 text-[9px] font-bold text-indigo-400">
                            <Clock className="w-3.5 h-3.5" /> {act.time || '指定なし'}
                          </div>
                          <h4 className="text-xs font-bold text-white leading-snug">{act.title}</h4>
                          <p className="text-[10px] text-slate-400 leading-relaxed">{act.description}</p>
                          {act.location && (
                            <span className="inline-flex items-center gap-0.5 text-[9px] text-slate-500">
                              <MapPin className="w-3 h-3" /> {act.location}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Sticky Actions panel */}
          <div className="border-t border-white/5 pt-4 bg-[#090b11]/80 backdrop-blur-md -mx-6 px-6 sticky bottom-0 space-y-3">
            <div className="grid grid-cols-2 gap-3 pb-4">
              <motion.button
                whileTap={{ scale: 0.98 }}
                onClick={handleRefine}
                disabled={saving}
                className="py-3.5 rounded-xl text-xs font-semibold text-slate-300 border border-white/10 hover:bg-white/5 hover:text-white transition-all flex items-center justify-center gap-1.5 cursor-pointer"
              >
                <MessageSquare className="w-4 h-4" /> 対話して微調整
              </motion.button>

              <motion.button
                whileTap={{ scale: 0.98 }}
                onClick={handleSavePlan}
                disabled={saving}
                className="py-3.5 rounded-xl text-xs font-semibold text-white animated-gradient shadow-lg flex items-center justify-center gap-1.5 cursor-pointer"
              >
                <Save className="w-4 h-4" /> 決定して保存
              </motion.button>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
}
