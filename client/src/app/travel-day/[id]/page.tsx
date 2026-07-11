'use client';

import React, { useEffect, useState, useRef, useMemo } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useAuthStore } from '@/stores/authStore';
import { useActivePlanStore } from '@/stores/activePlanStore';
import { dayAdvice } from '@/services/apiClient';
import { appPath } from '@/utils/pathHelper';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, Send, Sparkles, MapPin, Compass, Search, ExternalLink, HelpCircle } from 'lucide-react';

interface ChatMessage {
  id: number;
  type: 'user' | 'assistant' | 'system' | 'error';
  content: string;
  timestamp: Date;
  places?: any[];
  citations?: any[];
  routeInfo?: any;
}

const QUICK_SUGGESTIONS = [
  '近くのカフェを教えて ☕',
  '雨の日の代替プランは？ ☔',
  '美味しいランチのお店を探して 🍽️',
  '次の目的地への行き方は？ 🗺️',
  '周辺の観光スポットを教えて 🏯',
  '空いた時間の過ごし方は？ 🕒',
];

export default function TravelDayPage() {
  const router = useRouter();
  const params = useParams();
  const auth = useAuthStore();
  const activePlanStore = useActivePlanStore();

  const [plan, setPlan] = useState<any>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  
  const chatEndRef = useRef<HTMLDivElement>(null);
  const planId = params.id as string;

  const sessionId = useMemo(() => {
    return 'travel-day-' + 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }, []);

  useEffect(() => {
    if (!auth.isAuthenticated) {
      router.replace(appPath('/login'));
      return;
    }

    const init = async () => {
      try {
        const active = await activePlanStore.fetchActivePlan(auth.authHeader());
        if (!active || active.id !== planId) {
          await activePlanStore.activatePlan(planId, auth.authHeader());
        }

        const currentPlan = activePlanStore.activePlan || active;
        setPlan(currentPlan);

        const welcome: ChatMessage = {
          id: Date.now(),
          type: 'system',
          content: `旅行当日サポートを開始しました！プラン「${currentPlan?.title}」に基づき、近くのおすすめスポットや交通手段、天気のトラブルなどのご相談を承ります。`,
          timestamp: new Date(),
        };
        setMessages([welcome]);
      } catch (e) {
        console.error('Failed to init travel day chat:', e);
        router.push(appPath('/plans'));
      }
    };
    init();
  }, [planId, auth.isAuthenticated, router]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend || input).trim();
    if (!text || loading) return;

    if (!textToSend) setInput('');

    const userMsg: ChatMessage = {
      id: Date.now(),
      type: 'user',
      content: text,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const response = await dayAdvice({
        plan: plan,
        user_message: text,
        current_context: {},
        session_id: sessionId,
        authHeader: auth.authHeader(),
      });

      const assistantMsg: ChatMessage = {
        id: Date.now() + 1,
        type: 'assistant',
        content: response?.message || response?.reply || '周辺情報を検索してお答えしました。',
        timestamp: new Date(),
        places: response?.places || [],
        citations: response?.citations || [],
        routeInfo: response?.route_info || null,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (error) {
      console.error(error);
      const errMsg: ChatMessage = {
        id: Date.now() + 1,
        type: 'error',
        content: 'エラーが発生しました。時間を置いてもう一度ご相談ください。',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSend();
  };

  return (
    <div className="flex-1 flex flex-col justify-between relative overflow-hidden h-screen bg-[#f5f7fa]">
      {/* Header */}
      <div className="flex items-center gap-3 px-6 pt-6 pb-4 border-b border-gray-200 bg-white/90 backdrop-blur-md z-10">
        <button
          onClick={() => router.push(appPath('/main'))}
          className="p-2 rounded-xl border border-gray-200 bg-gray-50 text-slate-800 hover:bg-gray-100 transition-all cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div>
          <h1 className="text-xs font-bold text-slate-800 font-outfit truncate max-w-[180px]">
            {plan?.title || '旅行当日チャット'}
          </h1>
          <span className="text-[9px] text-teal-600 font-bold block tracking-wider uppercase flex items-center gap-1">
            <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
            Travel Day Assistant
          </span>
        </div>
      </div>

      {/* Message List Area */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col gap-2 max-w-[85%] ${
              msg.type === 'user' ? 'ml-auto items-end' : 'items-start'
            }`}
          >
            {/* Header / Icon */}
            <div className="flex items-center gap-1.5 text-[9px] text-slate-500 font-bold">
              {msg.type === 'user' ? (
                <span>あなた</span>
              ) : msg.type === 'system' ? (
                <span className="text-blue-600">システム</span>
              ) : msg.type === 'error' ? (
                <span className="text-rose-600">エラー</span>
              ) : (
                <span className="text-teal-600 flex items-center gap-0.5">
                  <Compass className="w-3 h-3" /> 当日アシスタント
                </span>
              )}
            </div>

            {/* Content box */}
            <div
              className={`rounded-2xl px-4 py-3 text-xs leading-relaxed ${
                msg.type === 'user'
                  ? 'bg-blue-600 text-white rounded-tr-none'
                  : msg.type === 'error'
                  ? 'bg-rose-50 border border-rose-200 text-rose-700 rounded-tl-none'
                  : 'bg-white border border-gray-200 text-slate-700 rounded-tl-none shadow-sm'
              }`}
            >
              {msg.content}
            </div>

            {/* Optional detailed places widgets */}
            {msg.places && msg.places.length > 0 && (
              <div className="w-full space-y-2 mt-2">
                {msg.places.map((place: any, pIdx: number) => (
                  <div
                    key={pIdx}
                    className="bg-white border border-gray-200 rounded-2xl p-3.5 space-y-1.5 shadow-sm flex flex-col justify-between"
                  >
                    <div>
                      <h4 className="text-xs font-bold text-slate-800 flex items-center gap-1">
                        <MapPin className="w-3.5 h-3.5 text-teal-600" />
                        {place.name}
                      </h4>
                      {place.description && (
                        <p className="text-[10px] text-slate-500 leading-normal mt-1">
                          {place.description}
                        </p>
                      )}
                    </div>

                    {place.rating && (
                      <span className="text-[9px] text-amber-600 font-bold">
                        ★ {place.rating} / 5.0
                      </span>
                    )}

                    {/* Find Google Map citations if matches */}
                    {msg.citations &&
                      msg.citations.find((c: any) => c.title?.includes(place.name)) && (
                        <a
                          href={msg.citations.find((c: any) => c.title?.includes(place.name)).url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="self-end text-[9px] text-blue-600 hover:text-blue-700 font-semibold flex items-center gap-0.5 mt-2"
                        >
                          Google Maps で開く <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex flex-col gap-2 max-w-[85%] items-start">
            <span className="text-[9px] text-teal-600 font-bold">当日アシスタント...</span>
            <div className="rounded-2xl px-4 py-3 bg-white border border-gray-200 text-slate-500 rounded-tl-none flex items-center gap-1.5 shadow-sm">
              <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-bounce delay-100" />
              <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-bounce delay-200" />
              <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-bounce delay-300" />
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Quick suggestions scroll */}
      <div className="px-6 py-2 flex gap-2 overflow-x-auto whitespace-nowrap bg-white border-t border-gray-200">
        {QUICK_SUGGESTIONS.map((s, idx) => (
          <button
            key={idx}
            onClick={() => handleSend(s)}
            disabled={loading}
            className="text-[10px] font-medium text-slate-600 border border-gray-200 hover:bg-gray-50 bg-white rounded-full px-3 py-1.5 cursor-pointer transition-all active:scale-95"
          >
            {s}
          </button>
        ))}
      </div>

      {/* Message input */}
      <div className="p-4 bg-[#f5f7fa] z-10">
        <form onSubmit={handleFormSubmit} className="flex gap-2.5">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="次のスケジュールや現地のおすすめを質問..."
            disabled={loading}
            className="flex-1 px-4 py-3 bg-white border border-gray-200 rounded-xl text-slate-800 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <motion.button
            whileTap={{ scale: 0.95 }}
            type="submit"
            disabled={loading || !input.trim()}
            className={`p-3 rounded-xl flex items-center justify-center shadow-md transition-all ${
              !input.trim() || loading
                ? 'bg-gray-100 text-gray-400 cursor-not-allowed border border-gray-200'
                : 'bg-blue-600 hover:bg-blue-700 text-white cursor-pointer'
            }`}
          >
            <Send className="w-4 h-4" />
          </motion.button>
        </form>
      </div>
    </div>
  );
}
