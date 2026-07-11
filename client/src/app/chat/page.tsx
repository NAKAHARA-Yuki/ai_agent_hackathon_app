'use client';

import React, { useEffect, useState, useRef, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/authStore';
import { generalChat } from '@/services/apiClient';
import { appPath } from '@/utils/pathHelper';
import BottomNav from '@/components/BottomNav';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Compass, User, RefreshCw, MapPin, Compass as CompassIcon, ShieldAlert } from 'lucide-react';

interface ChatMessage {
  id: number;
  type: 'user' | 'assistant' | 'system' | 'error';
  content: string;
  timestamp: Date;
  places?: any[];
  citations?: any[];
}

const QUICK_SUGGESTIONS = [
  { text: '週末に行ける温泉地を探して ♨️', label: '温泉旅行' },
  { text: '北海道のおいしい海鮮グルメスポットを教えて 🍣', label: 'グルメ旅' },
  { text: '京都の混雑を避けた穴場ルートは？ 🏯', label: '混雑回避' },
  { text: '予算5万円で行ける2泊3日のモデルプランは？ 💰', label: 'プラン相談' },
];

export default function GeneralChatPage() {
  const router = useRouter();
  const auth = useAuthStore();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(true);

  // Location details
  const [locationEnabled, setLocationEnabled] = useState(false);
  const [currentLocation, setCurrentLocation] = useState<any>(null);
  const [locationLoading, setLocationLoading] = useState(false);

  const chatEndRef = useRef<HTMLDivElement>(null);

  const sessionId = useMemo(() => {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
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

    // Default welcome message
    const welcome: ChatMessage = {
      id: Date.now(),
      type: 'system',
      content: 'こんにちは！AIコンシェルジュです。全国の観光スポット、おすすめの旅行ルート、現地の美味しいグルメについて何でも聞いてください。',
      timestamp: new Date(),
    };
    setMessages([welcome]);
  }, [auth.isAuthenticated, router]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const getCurrentLocation = async (): Promise<any> => {
    if (!navigator.geolocation) {
      throw new Error('お使いのブラウザは位置情報をサポートしていません。');
    }
    return new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(
        (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
        (err) => reject(new Error('位置情報の取得に失敗しました。利用許可されているかご確認ください。')),
        { enableHighAccuracy: true, timeout: 8000 }
      );
    });
  };

  const handleEnableLocation = async () => {
    setLocationLoading(true);
    try {
      const loc = await getCurrentLocation();
      setCurrentLocation(loc);
      setLocationEnabled(true);
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          type: 'system',
          content: '位置情報を有効にしました。現在地周辺の観光地やお食事処を詳しく調べられます！',
          timestamp: new Date(),
        },
      ]);
    } catch (e: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          type: 'error',
          content: e.message || '位置情報の有効化に失敗しました。',
          timestamp: new Date(),
        },
      ]);
    } finally {
      setLocationLoading(false);
    }
  };

  const handleDisableLocation = () => {
    setLocationEnabled(false);
    setCurrentLocation(null);
    setMessages((prev) => [
      ...prev,
      {
        id: Date.now(),
        type: 'system',
        content: '位置情報を無効にしました。',
        timestamp: new Date(),
      },
    ]);
  };

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend || input).trim();
    if (!text || loading) return;

    if (!textToSend) setInput('');
    setShowSuggestions(false);

    const userMsg: ChatMessage = {
      id: Date.now(),
      type: 'user',
      content: text,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      let locationPayload: { latitude: number; longitude: number } | undefined = undefined;
      if (locationEnabled && currentLocation) {
        locationPayload = {
          latitude: Number(currentLocation.latitude),
          longitude: Number(currentLocation.longitude),
        };
      }

      const response = await generalChat({
        message: text,
        user_id: auth.user?.id || 'guest',
        session_id: sessionId,
        location: locationPayload,
        authHeader: auth.authHeader(),
      });

      const assistantMsg: ChatMessage = {
        id: Date.now() + 1,
        type: 'assistant',
        content: response?.reply || response?.message || '情報を取得できませんでした。',
        timestamp: new Date(),
        places: response?.places || [],
        citations: response?.citations || [],
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e) {
      console.error(e);
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          type: 'error',
          content: 'エラーが発生しました。時間を置いてもう一度ご相談ください。',
          timestamp: new Date(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col justify-between relative overflow-hidden h-screen bg-[#f5f7fa]">
      {/* Top Header */}
      <div className="flex items-center justify-between px-6 pt-6 pb-4 border-b border-gray-200 bg-white/90 backdrop-blur-md z-10">
        <div>
          <h1 className="text-xl font-bold text-slate-800 font-outfit">AIコンシェルジュ</h1>
          <p className="text-[10px] text-slate-500">旅行に関するフリートーク相談を承ります</p>
        </div>

        {/* GPS Button */}
        <button
          onClick={locationEnabled ? handleDisableLocation : handleEnableLocation}
          disabled={locationLoading}
          className={`p-2.5 rounded-xl border flex items-center justify-center transition-all cursor-pointer ${
            locationEnabled
              ? 'border-emerald-200 bg-emerald-50 text-emerald-600'
              : 'border-gray-200 bg-white text-slate-500 hover:text-slate-800 shadow-sm'
          }`}
          title={locationEnabled ? '位置情報をオフにする' : '位置情報をオンにする'}
        >
          {locationLoading ? (
            <div className="animate-spin rounded-full h-4 w-4 border-2 border-t-transparent border-blue-500" />
          ) : (
            <MapPin className={`w-4 h-4 ${locationEnabled ? 'animate-pulse' : ''}`} />
          )}
        </button>
      </div>

      {/* Message List Area */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4 max-h-[75vh]">
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
                  ? 'bg-white text-blue-600 border border-blue-200 shadow-sm'
                  : msg.type === 'error'
                  ? 'bg-rose-50 border border-rose-200 text-rose-600 shadow-sm'
                  : 'bg-blue-50 border border-blue-200 text-blue-600 shadow-sm'
              }`}
            >
              {msg.type === 'user' ? <User className="w-4 h-4" /> : <CompassIcon className="w-4 h-4" />}
            </div>

            <div className="space-y-2">
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

              {/* Optional places / citations widgets */}
              {msg.places && msg.places.length > 0 && (
                <div className="w-full space-y-2 mt-2">
                  {msg.places.map((place: any, pIdx: number) => (
                    <div
                      key={pIdx}
                      className="bg-white border border-gray-200 rounded-2xl p-3 shadow-sm space-y-1"
                    >
                      <h4 className="text-xs font-bold text-slate-800 flex items-center gap-1">
                        <MapPin className="w-3.5 h-3.5 text-blue-600 animate-pulse" />
                        {place.name}
                      </h4>
                      {place.description && (
                        <p className="text-[10px] text-slate-500 leading-normal">
                          {place.description}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex gap-3 max-w-[85%]">
            <div className="w-7 h-7 rounded-xl bg-blue-50 border border-blue-200 text-blue-600 flex items-center justify-center text-xs shadow-sm">
              <CompassIcon className="w-4 h-4 animate-spin" />
            </div>
            <div className="rounded-2xl px-4 py-3 bg-white border border-gray-200 text-slate-500 rounded-tl-none flex items-center gap-1.5 shadow-sm">
              <span className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce delay-100" />
              <span className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce delay-200" />
              <span className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce delay-300" />
            </div>
          </div>
        )}
        <div ref={chatEndRef} />

        {/* Empty state Quick suggestions cards */}
        {showSuggestions && messages.length <= 1 && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="grid grid-cols-2 gap-3 pt-6"
          >
            {QUICK_SUGGESTIONS.map((s, idx) => (
              <button
                key={idx}
                onClick={() => handleSend(s.text)}
                className="bg-white border border-gray-200 hover:border-blue-300 hover:shadow-md rounded-2xl p-4 text-left cursor-pointer flex flex-col justify-between min-h-[100px] select-none shadow-sm transition-all"
              >
                <span className="text-[10px] text-blue-600 font-bold uppercase tracking-wider">
                  {s.label}
                </span>
                <span className="text-[11px] text-slate-600 font-medium leading-relaxed">
                  {s.text}
                </span>
              </button>
            ))}
          </motion.div>
        )}
      </div>

      {/* Message input area */}
      <div className="p-4 bg-[#f5f7fa] border-t border-gray-200 z-10 flex flex-col gap-3">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex gap-2.5"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="全国のおすすめスポットや計画方法を聞く..."
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

      {/* Bottom Nav */}
      <BottomNav />
    </div>
  );
}
