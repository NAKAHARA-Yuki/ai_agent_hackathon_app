'use client';

import React, { useEffect, useState, useRef, useMemo } from 'react';
import { useRouter, useParams, useSearchParams } from 'next/navigation';
import { useAuthStore } from '@/stores/authStore';
import { modifyPlan, agentChat, planDetail, createPlan, Plan } from '@/services/apiClient';
import { transportLabel, transportIcon, formatDuration, formatDistance } from '@/utils/transportHelpers';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, Send, Save, MessageSquare, Calendar, Sparkles, Check, Clock, MapPin, User, Compass } from 'lucide-react';


interface ChatMessage {
  id: number;
  type: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  updatedPlan?: any;
}

export default function PlanChatPage() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const auth = useAuthStore();

  const [activeTab, setActiveTab] = useState<'chat' | 'itinerary'>('chat');
  const [originalPlan, setOriginalPlan] = useState<Plan | null>(null);
  const [currentPlan, setCurrentPlan] = useState<any>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState('');

  const chatEndRef = useRef<HTMLDivElement>(null);
  const planId = params.id as string;

  // Generate UUID for session tracking
  const sessionId = useMemo(() => {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }, []);

  useEffect(() => {
    if (!auth.isAuthenticated) {
      router.replace('/login');
      return;
    }

    const init = async () => {
      try {
        const plan = await planDetail(planId, auth.authHeader());
        setOriginalPlan(plan);
        setCurrentPlan({ ...plan });

        // Welcome message
        const welcome: ChatMessage = {
          id: Date.now(),
          type: 'system',
          content: `こんにちは！プラン「${plan.title}」を調整するお手伝いをします。修正したい箇所や、「〇〇を追加して」などのご要望を教えてください。`,
          timestamp: new Date(),
        };
        setMessages([welcome]);
      } catch (e) {
        console.error('Failed to load plan for chat:', e);
        router.push('/plans');
      }
    };
    init();
  }, [planId, auth.isAuthenticated, router]);

  // Scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const showToast = (message: string) => {
    setToast(message);
    setTimeout(() => setToast(''), 2500);
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput('');

    // Append user message
    const userMsg: ChatMessage = {
      id: Date.now(),
      type: 'user',
      content: userMessage,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      // Modify plan API
      const response = await modifyPlan({
        plan: currentPlan,
        change_requests: userMessage,
        session_id: sessionId,
        authHeader: auth.authHeader(),
      });

      const updated = response?.updated_plan || response;
      if (updated && typeof updated === 'object') {
        // Merge or replace
        setCurrentPlan((prev: any) => ({
          ...prev,
          ...updated,
          // Guard and merge nested properties
          itinerary: updated.itinerary || prev.itinerary || [],
          places: updated.places || prev.places || [],
        }));
        showToast('旅程プランが更新されました！');
      }

      // Add assistant message
      const assistantMsg: ChatMessage = {
        id: Date.now() + 1,
        type: 'assistant',
        content: response?.message || response?.summary || 'ご要望に基づいてプランを更新しました。「旅程」タブからご確認ください。',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e: any) {
      console.error(e);
      // Fallback to simple chat agent
      try {
        const response = await agentChat({
          message: `現在のプラン「${currentPlan?.title}」について以下の要望があります: ${userMessage}`,
          user_id: auth.user?.id || 'guest',
          session_id: sessionId,
          authHeader: auth.authHeader(),
        });
        
        const assistantMsg: ChatMessage = {
          id: Date.now() + 1,
          type: 'assistant',
          content: response?.reply || '応答の取得に失敗しました。',
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, assistantMsg]);
      } catch (err) {
        showToast('通信エラーが発生しました');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (saving || !currentPlan) return;
    setSaving(true);
    try {
      const payload = {
        title: currentPlan.title,
        text: currentPlan.text || currentPlan.brief || '',
        places: currentPlan.places || [],
        route_info: currentPlan.route_info || null,
        itinerary: currentPlan.itinerary || [],
        image_base64: currentPlan.image_base64 || originalPlan?.image_base64 || null,
        image_mime_type: currentPlan.image_mime_type || originalPlan?.image_mime_type || null,
        status: 'draft',
      };
      // Overwrite the existing document
      await createPlan({ ...payload, id: planId }, auth.authHeader());
      showToast('プランを正常に保存しました！');
      setTimeout(() => {
        router.push(`/plans/${planId}`);
      }, 1000);
    } catch (e) {
      console.error(e);
      showToast('保存に失敗しました');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col justify-between relative overflow-hidden h-screen bg-white">
      {/* Header */}
      <div className="flex items-center justify-between px-6 pt-6 pb-4 border-b border-gray-200 bg-white/80 backdrop-blur-md z-10">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push(`/plans/${planId}`)}
            className="p-2 rounded-xl border border-gray-200 bg-gray-50 text-slate-800 hover:bg-gray-100 transition-all cursor-pointer"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h1 className="text-xs font-bold text-slate-800 font-outfit truncate max-w-[150px]">
              {currentPlan?.title || 'プラン調整'}
            </h1>
            <span className="text-[9px] text-slate-500 font-bold block tracking-wider uppercase">
              AI BRUSHUP
            </span>
          </div>
        </div>

        <button
          onClick={handleSave}
          disabled={saving}
          className="px-3.5 py-2 rounded-xl text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 shadow-md flex items-center gap-1.5 cursor-pointer"
        >
          <Save className="w-3.5 h-3.5" />
          {saving ? '保存中' : '保存'}
        </button>
      </div>

      {/* Dynamic Selector Tabs */}
      <div className="flex border-b border-gray-200 bg-white px-6 py-2 gap-2">
        <button
          onClick={() => setActiveTab('chat')}
          className={`flex-1 py-2 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 cursor-pointer transition-all ${
            activeTab === 'chat'
              ? 'bg-blue-50 border border-blue-200 text-blue-600 font-bold shadow-sm'
              : 'text-slate-500 bg-gray-50 border border-transparent hover:bg-gray-100'
          }`}
        >
          <MessageSquare className="w-3.5 h-3.5" /> チャット
        </button>
        <button
          onClick={() => setActiveTab('itinerary')}
          className={`flex-1 py-2 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 cursor-pointer transition-all ${
            activeTab === 'itinerary'
              ? 'bg-blue-50 border border-blue-200 text-blue-600 font-bold shadow-sm'
              : 'text-slate-500 bg-gray-50 border border-transparent hover:bg-gray-100'
          }`}
        >
          <Calendar className="w-3.5 h-3.5" /> 旅程プレビュー
        </button>
      </div>

      {/* CHAT TAB PANEL */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {activeTab === 'chat' ? (
          <>
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex gap-3 max-w-[85%] ${msg.type === 'user' ? 'ml-auto flex-row-reverse' : ''}`}
              >
                <div
                  className={`w-7 h-7 rounded-xl flex items-center justify-center flex-shrink-0 text-xs font-bold ${
                    msg.type === 'user'
                      ? 'bg-blue-600 text-white'
                      : msg.type === 'system'
                      ? 'bg-slate-100 text-blue-600 border border-blue-200'
                      : 'bg-blue-50 border border-blue-100 text-blue-600'
                  }`}
                >
                  {msg.type === 'user' ? <User className="w-4 h-4" /> : <Compass className="w-4 h-4" />}
                </div>

                <div
                  className={`rounded-2xl px-4 py-3 text-xs leading-relaxed ${
                    msg.type === 'user'
                      ? 'bg-blue-600 text-white rounded-tr-none'
                      : 'bg-gray-100 border border-gray-200 text-slate-800 rounded-tl-none'
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex gap-3 max-w-[85%]">
                <div className="w-7 h-7 rounded-xl bg-blue-50 border border-blue-100 text-blue-600 flex items-center justify-center text-xs">
                  <Compass className="w-4 h-4 animate-spin" />
                </div>
                <div className="rounded-2xl px-4 py-3 text-xs bg-gray-100 border border-gray-200 text-slate-500 rounded-tl-none flex items-center gap-1.5">
                  <span className="w-1 h-1 bg-slate-500 rounded-full animate-bounce delay-100" />
                  <span className="w-1 h-1 bg-slate-500 rounded-full animate-bounce delay-200" />
                  <span className="w-1 h-1 bg-slate-500 rounded-full animate-bounce delay-300" />
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </>
        ) : (
          /* ITINERARY PREVIEW PANEL */
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-6 pb-24"
          >
            {currentPlan?.text && (
              <div className="bg-white border border-gray-200 shadow-sm rounded-2xl p-4 space-y-1">
                <h3 className="text-[10px] font-bold text-slate-500 tracking-wider">SUMMARY</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-outfit whitespace-pre-wrap">{currentPlan.text}</p>
              </div>
            )}

            {currentPlan?.itinerary && currentPlan.itinerary.length > 0 ? (
              <div className="space-y-6 pl-4 border-l border-gray-200 relative">
                {currentPlan.itinerary.map((day: any, dIdx: number) => (
                  <div key={dIdx} className="space-y-4 relative">
                    <div className="absolute -left-[25px] top-1.5 w-4 h-4 rounded-full border border-blue-500 bg-white flex items-center justify-center text-[8px] font-bold text-blue-600 shadow-md">
                      D{day.day || dIdx + 1}
                    </div>
                    <div className="font-bold text-xs text-slate-800 pl-2">Day {day.day || dIdx + 1}</div>
                    
                    <div className="space-y-3 pl-2">
                      {(day.items || day.activities || []).map((item: any, iIdx: number) => (
                        <div key={iIdx} className="space-y-2">
                          <div className="bg-gray-50 border border-gray-200 rounded-xl p-3.5 space-y-1">
                            <div className="flex items-center gap-1.5 text-[9px] font-bold text-blue-600">
                              <Clock className="w-3.5 h-3.5" /> {item.time || '時間指定なし'}
                            </div>
                            <h4 className="text-xs font-bold text-slate-800 leading-snug">{item.title}</h4>
                            {(item.detail || item.description) && (
                              <p className="text-[10px] text-slate-650 leading-relaxed mt-1">
                                {item.detail || item.description}
                              </p>
                            )}
                            {item.location && (
                              <span className="inline-flex items-center gap-0.5 text-[9px] text-slate-500 mt-1">
                                <MapPin className="w-3 h-3" /> {item.location}
                              </span>
                            )}
                          </div>

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
            ) : (
              <p className="text-xs text-slate-500 text-center py-12">旅程はありません。チャットで要望を送ってください。</p>
            )}
          </motion.div>
        )}
      </div>

      {/* Bottom Message Input (Sticky, only show on Chat tab) */}
      {activeTab === 'chat' && (
        <div className="border-t border-gray-200 bg-white p-4 z-10 flex gap-2">
          <form onSubmit={handleSend} className="w-full flex gap-2.5">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="例: 2日目を小樽運河の散策に変更して"
              disabled={loading}
              className="flex-1 px-4 py-3 border border-gray-200 bg-gray-50 text-slate-800 rounded-xl text-xs focus:bg-white focus:border-blue-500 focus:outline-none transition-all"
            />
            <motion.button
              whileTap={{ scale: 0.95 }}
              type="submit"
              disabled={loading || !input.trim()}
              className={`p-3 rounded-xl flex items-center justify-center shadow-lg transition-all ${
                !input.trim() || loading
                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed border border-gray-200'
                  : 'bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-700 hover:to-blue-600 text-white cursor-pointer'
              }`}
            >
              <Send className="w-4 h-4" />
            </motion.button>
          </form>
        </div>
      )}

      {/* Floating toast notification */}
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
    </div>
  );
}
