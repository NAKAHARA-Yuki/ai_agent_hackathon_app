'use client';

import React, { useEffect, useState, useRef, useMemo } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useAuthStore } from '@/stores/authStore';
import { getMemory, listPlans, getMemoryVideoStatus } from '@/services/apiClient';
import { appPath } from '@/utils/pathHelper';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, Play, Calendar, Film, Image as ImageIcon, MapPin, Sparkles, ShieldAlert, CheckCircle2 } from 'lucide-react';

interface MemoryImage {
  image_base64: string;
  image_mime_type: string;
}

export default function MemoryDetailPage() {
  const router = useRouter();
  const params = useParams();
  const auth = useAuthStore();

  const [memory, setMemory] = useState<any>(null);
  const [plans, setPlans] = useState<any[]>([]);
  const [videoJobs, setVideoJobs] = useState<any[]>([]);
  const [allDone, setAllDone] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [selectedPhoto, setSelectedPhoto] = useState<string | null>(null);

  const memoryId = params.id as string;
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  const fetchDetails = async () => {
    try {
      setError('');
      const [memData, planData] = await Promise.all([
        getMemory(memoryId, auth.authHeader()),
        listPlans(auth.authHeader()),
      ]);

      setMemory(memData);
      setPlans(Array.isArray(planData.items) ? planData.items : []);
      setVideoJobs(Array.isArray(memData.video_jobs) ? memData.video_jobs : []);
      
      const done = memData.primary_video_url
        ? true
        : memData.video_jobs && Array.isArray(memData.video_jobs)
        ? memData.video_jobs.every((j: any) => j.done)
        : true;

      setAllDone(done);
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
    fetchDetails();
  }, [memoryId, auth.isAuthenticated, router]);

  // Video Polling logic
  useEffect(() => {
    if (loading || allDone || !memoryId) return;

    pollTimerRef.current = setInterval(async () => {
      try {
        const s = await getMemoryVideoStatus(memoryId, auth.authHeader());
        setVideoJobs(s.video_jobs || []);
        setAllDone(!!s.all_done);

        if (s.primary_video_url || s.video_urls) {
          setMemory((prev: any) => ({
            ...prev,
            primary_video_url: s.primary_video_url || prev?.primary_video_url,
            video_urls: s.video_urls || prev?.video_urls,
          }));
        }

        if (s.all_done) {
          if (pollTimerRef.current) clearInterval(pollTimerRef.current);
        }
      } catch (e) {
        // Suppress transient errors
      }
    }, 5000);

    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [loading, allDone, memoryId, auth.authHeader]);

  const planTitle = useMemo(() => {
    if (!memory) return '';
    if (memory.title) return memory.title;
    const p = plans.find((x) => x.id === memory.plan_id);
    return p?.title || memory.plan_id || '';
  }, [memory, plans]);

  const videoUrlsList = useMemo(() => {
    const urls: string[] = [];
    if (memory?.video_urls && Array.isArray(memory.video_urls)) {
      memory.video_urls.forEach((u: string) => {
        if (u && !urls.includes(u)) urls.push(u);
      });
    }
    videoJobs.forEach((j: any) => {
      if (j?.video_public_url && !urls.includes(j.video_public_url)) {
        urls.push(j.video_public_url);
      }
    });

    const primary = memory?.primary_video_url;
    if (primary) {
      const idx = urls.indexOf(primary);
      if (idx > 0) {
        urls.splice(idx, 1);
        urls.unshift(primary);
      } else if (idx === -1) {
        urls.unshift(primary);
      }
    }
    return urls;
  }, [memory, videoJobs]);

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

  if (loading) {
    return (
      <div className="flex-1 flex justify-center items-center">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (error || !memory) {
    return (
      <div className="flex-1 flex flex-col justify-center items-center px-6 text-center space-y-4">
        <ShieldAlert className="w-8 h-8 text-rose-600" />
        <p className="text-slate-600 text-sm">{error || '思い出が見つかりませんでした。'}</p>
        <button
          onClick={() => router.push(appPath('/memories'))}
          className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 transition-all cursor-pointer"
        >
          アルバム一覧へ戻る
        </button>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col justify-start px-6 py-8 relative overflow-y-auto max-h-screen bg-[#f5f7fa] text-slate-800">
      {/* Background glowing decorations */}
      <div className="absolute top-1/3 left-1/10 w-72 h-72 bg-blue-600/5 rounded-full blur-3xl -z-10" />

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <button
          onClick={() => router.push(appPath('/memories'))}
          className="p-2 rounded-xl border border-gray-200 bg-gray-50 hover:bg-gray-100 text-slate-800 transition-all cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <span className="text-xs font-bold text-slate-400 tracking-wider font-outfit">
          ALBUM DETAIL
        </span>
        <div className="w-8" />
      </div>

      <div className="space-y-6 pb-24">
        {/* Album Header Info */}
        <div className="space-y-2">
          <h1 className="text-lg font-bold text-slate-800 leading-snug">{planTitle}</h1>
          {(memory.trip_start_date || memory.trip_end_date) && (
            <p className="text-[10px] text-slate-500 font-mono flex items-center gap-1">
              <Calendar className="w-3.5 h-3.5" />
              {fmtDate(memory.trip_start_date)} ~ {fmtDate(memory.trip_end_date)}
            </p>
          )}
        </div>

        {/* Video slideshow player */}
        <div className="space-y-3">
          <h3 className="text-xs font-bold text-slate-700 flex items-center gap-1">
            <Film className="w-4 h-4 text-blue-600" /> スライドショー動画
          </h3>

          {videoUrlsList.length > 0 ? (
            <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden aspect-video relative shadow-sm flex items-center justify-center">
              <video
                src={videoUrlsList[0]}
                controls
                playsInline
                className="w-full h-full object-contain"
                poster={
                  memory.images && memory.images.length > 0
                    ? `data:${memory.images[0].image_mime_type || 'image/png'};base64,${memory.images[0].image_base64}`
                    : undefined
                }
              />
            </div>
          ) : !allDone ? (
            /* Video generating / waiting status */
            <div className="bg-blue-50/50 border border-blue-200 rounded-2xl p-6 text-center space-y-4 shadow-sm">
              <div className="relative w-12 h-12 mx-auto">
                <div className="animate-spin rounded-full h-full w-full border-2 border-blue-500 border-t-transparent" />
                <Film className="w-5 h-5 text-blue-600 absolute inset-3.5 animate-pulse" />
              </div>
              <div>
                <p className="text-xs font-bold text-slate-800">AIスライドショー動画を生成中...</p>
                <p className="text-[9px] text-slate-500 mt-1 leading-relaxed">
                  アップロードされた写真から自動で想い出ムービーを作成しています。<br />
                  このまま少々お待ちください。
                </p>
              </div>
            </div>
          ) : (
            <div className="bg-white border border-gray-200 rounded-2xl py-8 text-center text-xs text-slate-500 shadow-sm">
              動画生成のリクエストがありません。
            </div>
          )}
        </div>

        {/* Photos grid */}
        {memory.images && memory.images.length > 0 && (
          <div className="space-y-3">
            <h3 className="text-xs font-bold text-slate-700 flex items-center gap-1">
              <ImageIcon className="w-4 h-4 text-blue-600" /> 想い出の写真
            </h3>

            <div className="grid grid-cols-3 gap-2">
              {memory.images.map((img: MemoryImage, idx: number) => {
                const src = `data:${img.image_mime_type || 'image/png'};base64,${img.image_base64}`;
                return (
                  <motion.div
                    key={idx}
                    whileTap={{ scale: 0.96 }}
                    onClick={() => setSelectedPhoto(src)}
                    className="aspect-square bg-gray-100 rounded-xl overflow-hidden cursor-pointer shadow-sm hover:opacity-90 transition-opacity border border-gray-200"
                  >
                    <img src={src} alt={`Photo ${idx + 1}`} className="w-full h-full object-cover" />
                  </motion.div>
                );
              })}
            </div>
          </div>
        )}

        {/* Itinerary details */}
        {memory.itinerary && memory.itinerary.length > 0 && (
          <div className="space-y-3">
            <h3 className="text-xs font-bold text-slate-700 flex items-center gap-1">
              <MapPin className="w-4 h-4 text-blue-600" /> 当日の活動ルート
            </h3>
            <div className="bg-white border border-gray-200 rounded-2xl p-4 space-y-4 shadow-sm">
              {memory.itinerary.map((day: any, dIdx: number) => (
                <div key={dIdx} className="space-y-2 border-b border-gray-200 last:border-b-0 pb-3 last:pb-0">
                  <div className="text-[10px] font-bold text-blue-600 uppercase tracking-wider">
                    Day {day.day || dIdx + 1}
                  </div>
                  <div className="space-y-1.5">
                    {(day.items || day.activities || []).map((item: any, iIdx: number) => (
                      <div key={iIdx} className="text-xs flex items-start gap-1.5 leading-relaxed text-slate-700">
                        <span className="font-semibold text-slate-800">•</span>
                        <div>
                          <span className="font-semibold text-slate-800 text-xs">{item.title}</span>
                          {item.detail && <span className="text-[10px] text-slate-500 ml-1.5">— {item.detail}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Photo expand dialog */}
      <AnimatePresence>
        {selectedPhoto && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSelectedPhoto(null)}
            className="fixed inset-0 bg-black/95 z-50 flex items-center justify-center p-4 cursor-zoom-out"
          >
            <motion.div
              initial={{ scale: 0.95 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0.95 }}
              className="max-w-full max-h-full overflow-hidden flex items-center justify-center"
            >
              <img src={selectedPhoto} alt="Expanded" className="max-w-full max-h-[85vh] object-contain rounded-xl shadow-2xl" />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
