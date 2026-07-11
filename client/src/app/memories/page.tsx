'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/authStore';
import { listMemories, listPlans, createMemory, Memory, Plan } from '@/services/apiClient';
import { appPath } from '@/utils/pathHelper';
import BottomNav from '@/components/BottomNav';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Image, Calendar, Trash2, ShieldAlert, X, Upload } from 'lucide-react';

export default function MemoriesPage() {
  const router = useRouter();
  const auth = useAuthStore();

  const [memories, setMemories] = useState<Memory[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Modal / Form state
  const [showModal, setShowModal] = useState(false);
  const [selectedPlanId, setSelectedPlanId] = useState('');
  const [tripStart, setTripStart] = useState('');
  const [tripEnd, setTripEnd] = useState('');
  const [images, setImages] = useState<(any | null)[]>([null, null, null]);
  const [saving, setSaving] = useState(false);

  const fetchMemoriesAndPlans = async () => {
    try {
      setError('');
      const [memData, planData] = await Promise.all([
        listMemories(auth.authHeader()),
        listPlans(auth.authHeader()),
      ]);
      setMemories(Array.isArray(memData.items) ? memData.items : []);
      setPlans(Array.isArray(planData.items) ? planData.items : []);
    } catch (e) {
      console.error(e);
      setError('読み込みに失敗しました。');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!auth.isAuthenticated) {
      router.replace(appPath('/login'));
      return;
    }
    fetchMemoriesAndPlans();
  }, [auth.isAuthenticated, router]);

  const openAddModal = () => {
    setSelectedPlanId(plans[0]?.id || '');
    setTripStart('');
    setTripEnd('');
    setImages([null, null, null]);
    setShowModal(true);
  };

  const toBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const res = String(reader.result || '');
        const idx = res.indexOf(',');
        resolve(idx >= 0 ? res.slice(idx + 1) : res);
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  };

  const handleFileChange = async (idx: number, e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) {
      const nextImages = [...images];
      nextImages[idx] = null;
      setImages(nextImages);
      return;
    }

    try {
      const b64 = await toBase64(file);
      const nextImages = [...images];
      nextImages[idx] = {
        image_base64: b64,
        image_mime_type: file.type || 'image/png',
        preview: URL.createObjectURL(file),
      };
      setImages(nextImages);
    } catch (err) {
      console.error('File reading failed:', err);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    const validImgs = images.filter((img) => img !== null).map((img) => ({
      image_base64: img.image_base64,
      image_mime_type: img.image_mime_type,
    }));

    if (!selectedPlanId || validImgs.length === 0 || saving) return;

    setSaving(true);
    try {
      const payload: any = { plan_id: selectedPlanId, images: validImgs };
      if (tripStart) payload.trip_start_date = tripStart;
      if (tripEnd) payload.trip_end_date = tripEnd;

      await createMemory(payload, auth.authHeader());
      setShowModal(false);
      await fetchMemoriesAndPlans();
    } catch (err) {
      console.error(err);
      alert('登録に失敗しました。時間をおいて再試行してください。');
    } finally {
      setSaving(false);
    }
  };

  const fmtDate = (s?: string) => {
    if (!s) return '';
    try {
      const d = new Date(s);
      if (isNaN(d.getTime())) return s;
      return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`;
    } catch {
      return s;
    }
  };

  const getMemoryRange = (mem: Memory) => {
    if (mem.trip_start_date || mem.trip_end_date) {
      return `${fmtDate(mem.trip_start_date)} ~ ${fmtDate(mem.trip_end_date)}`;
    }
    return fmtDate(mem.created_at);
  };

  const getMemoryTitle = (mem: Memory) => {
    if (mem.title) return mem.title;
    const matchedPlan = plans.find((p) => p.id === mem.plan_id);
    return matchedPlan ? `${matchedPlan.title}の思い出` : '思い出';
  };

  const canSave = selectedPlanId && images.some((img) => img !== null);

  return (
    <div className="flex-1 flex flex-col justify-between px-6 pt-8 relative overflow-hidden">
      {/* Background glowing decorations */}
      <div className="absolute bottom-1/4 right-1/10 w-72 h-72 bg-indigo-600/5 rounded-full blur-3xl -z-10" />

      {/* Scrollable Container */}
      <div className="flex-1 overflow-y-auto pr-1 pb-6 space-y-6 max-h-[85vh]">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-xl font-bold text-white font-outfit">思い出アルバム</h1>
            <p className="text-[10px] text-slate-400">訪れた場所の記録とスライド動画</p>
          </div>
          {plans.length > 0 && (
            <button
              onClick={openAddModal}
              className="p-2 rounded-xl bg-indigo-600 text-white hover:bg-indigo-500 transition-all flex items-center gap-1 shadow-md cursor-pointer text-xs font-semibold"
            >
              <Plus className="w-4 h-4" /> 追加
            </button>
          )}
        </div>

        {/* Loading & Error */}
        {loading ? (
          <div className="text-center py-12 text-xs text-slate-500">読み込み中...</div>
        ) : error ? (
          <div className="glass-panel border-rose-900/50 p-4 rounded-2xl flex items-center gap-3">
            <ShieldAlert className="w-5 h-5 text-rose-400 flex-shrink-0" />
            <span className="text-xs text-rose-400 font-medium">{error}</span>
          </div>
        ) : memories.length > 0 ? (
          <div className="grid grid-cols-1 gap-4">
            {memories.map((mem) => {
              const hasImages = mem.images && mem.images.length > 0 && mem.images[0].image_base64;
              const firstImg = hasImages
                ? `data:${mem.images[0].image_mime_type || 'image/png'};base64,${mem.images[0].image_base64}`
                : '';

              return (
                <div
                  key={mem.id}
                  onClick={() => router.push(appPath(`/memories/${mem.id}`))}
                  className="glass-panel-interactive rounded-2xl overflow-hidden cursor-pointer shadow-lg flex"
                >
                  {/* Image Thumbnail */}
                  <div className="w-28 h-28 flex-shrink-0 bg-slate-900 flex items-center justify-center relative">
                    {hasImages ? (
                      <img src={firstImg} alt="Thumbnail" className="w-full h-full object-cover" />
                    ) : (
                      <Image className="w-6 h-6 text-slate-700" />
                    )}
                    {mem.images && mem.images.length > 1 && (
                      <span className="absolute bottom-2 right-2 bg-black/70 text-white text-[9px] font-bold px-1.5 py-0.5 rounded-md font-mono">
                        +{mem.images.length - 1}
                      </span>
                    )}
                  </div>

                  {/* Text Description */}
                  <div className="p-4 flex flex-col justify-between flex-1 min-w-0">
                    <div className="space-y-1">
                      <h3 className="text-xs font-bold text-white truncate">
                        {getMemoryTitle(mem)}
                      </h3>
                      <p className="text-[9px] text-slate-400 leading-normal flex items-center gap-0.5 font-mono">
                        <Calendar className="w-3.5 h-3.5" />
                        {getMemoryRange(mem)}
                      </p>
                    </div>
                    <span className="text-[8px] text-indigo-400 font-bold self-end hover:underline">
                      アルバムを開く &rarr;
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="glass-panel rounded-2xl py-16 px-6 text-center space-y-4">
            <Image className="w-8 h-8 text-slate-500 mx-auto" />
            <div>
              <p className="text-xs text-slate-400">登録された想い出がありません。</p>
              <p className="text-[10px] text-slate-500 mt-1">旅行先で撮った写真をアップロードしてアルバムにしましょう。</p>
            </div>
            {plans.length > 0 ? (
              <button
                onClick={openAddModal}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 transition-all shadow-md cursor-pointer"
              >
                想い出アルバムを作る
              </button>
            ) : (
              <p className="text-[10px] text-slate-600">※思い出の作成には旅行プランの登録が必要です。</p>
            )}
          </div>
        )}
      </div>

      {/* NEW MEMORY UPLOAD MODAL */}
      <AnimatePresence>
        {showModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-slate-950/70 backdrop-blur-sm z-50 flex items-center justify-center p-6"
          >
            <motion.div
              initial={{ scale: 0.95, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 20 }}
              className="w-full max-w-sm glass-panel rounded-2xl p-6 shadow-2xl relative max-h-[85vh] overflow-y-auto"
            >
              <button
                onClick={() => setShowModal(false)}
                className="absolute top-4 right-4 p-1.5 rounded-lg text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>

              <div className="text-center mb-6">
                <h2 className="text-base font-bold text-white font-outfit">思い出の追加</h2>
                <p className="text-[10px] text-slate-400 mt-1">
                  旅行の計画と写真を選択してアルバムを作成します。
                </p>
              </div>

              <form onSubmit={handleSave} className="space-y-4">
                {/* Plan Selector */}
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                    対象の旅行プラン
                  </label>
                  <select
                    value={selectedPlanId}
                    onChange={(e) => setSelectedPlanId(e.target.value)}
                    className="w-full px-3 py-2.5 glass-input text-xs text-white bg-slate-900 border border-white/5 focus:outline-none rounded-xl"
                  >
                    {plans.map((p) => (
                      <option key={p.id} value={p.id} className="bg-slate-950 text-white">
                        {p.title}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Date Fields */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-slate-400 block">開始日</label>
                    <input
                      type="date"
                      value={tripStart}
                      onChange={(e) => setTripStart(e.target.value)}
                      className="w-full px-3 py-2 glass-input text-xs text-white focus:outline-none rounded-xl"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-slate-400 block">終了日</label>
                    <input
                      type="date"
                      value={tripEnd}
                      onChange={(e) => setTripEnd(e.target.value)}
                      className="w-full px-3 py-2 glass-input text-xs text-white focus:outline-none rounded-xl"
                    />
                  </div>
                </div>

                {/* Images Upload */}
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                    思い出の写真（最大3枚）
                  </label>

                  <div className="grid grid-cols-3 gap-2">
                    {images.map((img, idx) => (
                      <div
                        key={idx}
                        className="aspect-square bg-white/5 border border-dashed border-white/10 rounded-xl relative flex flex-col items-center justify-center cursor-pointer hover:bg-white/10 transition-colors overflow-hidden"
                      >
                        {img?.preview ? (
                          <img src={img.preview} alt="Upload" className="w-full h-full object-cover" />
                        ) : (
                          <>
                            <Upload className="w-4 h-4 text-slate-500 mb-1" />
                            <span className="text-[8px] text-slate-500 font-bold">写真 {idx + 1}</span>
                          </>
                        )}
                        <input
                          type="file"
                          accept="image/*"
                          onChange={(e) => handleFileChange(idx, e)}
                          className="absolute inset-0 opacity-0 cursor-pointer"
                        />
                      </div>
                    ))}
                  </div>
                </div>

                {/* Save button */}
                <motion.button
                  whileTap={{ scale: 0.98 }}
                  type="submit"
                  disabled={!canSave || saving}
                  className={`w-full py-3.5 rounded-xl text-xs font-semibold text-white shadow-lg flex justify-center items-center gap-1.5 ${
                    !canSave || saving
                      ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-white/5'
                      : 'animated-gradient cursor-pointer'
                  }`}
                >
                  {saving ? '登録中...' : '登録して保存'}
                </motion.button>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Bottom Navigation */}
      <BottomNav />
    </div>
  );
}
