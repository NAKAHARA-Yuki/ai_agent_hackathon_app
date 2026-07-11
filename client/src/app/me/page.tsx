'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/authStore';
import BottomNav from '@/components/BottomNav';
import { motion, AnimatePresence } from 'framer-motion';
import { User, LogOut, Save, Plus, X, Calendar, MapPin, DollarSign, RefreshCw } from 'lucide-react';

interface ProfileState {
  display_name: string;
  age: string | number;
  birthdate: string;
  gender: string;
  hobbies: string[];
  location: string;
  budget: string;
  notes: string;
}

export default function MyPage() {
  const router = useRouter();
  const auth = useAuthStore();

  const [profile, setProfile] = useState<ProfileState>({
    display_name: '',
    age: '',
    birthdate: '',
    gender: '',
    hobbies: [],
    location: '',
    budget: '',
    notes: '',
  });

  const [hobbyInput, setHobbyInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState('');

  const loadProfile = async () => {
    try {
      const resp = await fetch('/api/profile', {
        headers: { 'Content-Type': 'application/json', ...auth.authHeader() },
      });
      if (resp.ok) {
        const data = await resp.json();
        const p = data.profile || {};
        
        let rawHobbies: string[] = [];
        if (Array.isArray(p.hobbies)) {
          rawHobbies = p.hobbies;
        } else if (typeof p.hobbies === 'string') {
          rawHobbies = p.hobbies.split(',').map((s: string) => s.trim()).filter(Boolean);
        }

        setProfile({
          display_name: p.display_name || data.name || auth.user?.name || '',
          age: p.age || '',
          birthdate: p.birthdate || '',
          gender: p.gender || '',
          hobbies: rawHobbies,
          location: p.location || '',
          budget: p.budget || '',
          notes: p.notes || '',
        });
      }
    } catch (e) {
      console.error('Failed to load profile:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!auth.isAuthenticated) {
      router.replace('/login');
      return;
    }
    loadProfile();
  }, [auth.isAuthenticated, router]);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(''), 2500);
  };

  const handleBirthdateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    let calculatedAge = '';

    if (val) {
      const today = new Date();
      const [y, m, d] = val.split('-').map(Number);
      if (y && m && d) {
        let age = today.getFullYear() - y;
        const hasBirthdayPassed =
          today.getMonth() + 1 > m || (today.getMonth() + 1 === m && today.getDate() >= d);
        if (!hasBirthdayPassed) age -= 1;
        if (age >= 0 && age <= 120) calculatedAge = String(age);
      }
    }

    setProfile((prev) => ({
      ...prev,
      birthdate: val,
      age: calculatedAge,
    }));
  };

  const handleAddHobby = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const val = hobbyInput.trim();
      if (!val) return;
      if (profile.hobbies.length >= 10) {
        showToast('趣味は最大10件まで登録できます');
        return;
      }
      if (profile.hobbies.includes(val)) {
        setHobbyInput('');
        return;
      }

      setProfile((prev) => ({
        ...prev,
        hobbies: [...prev.hobbies, val],
      }));
      setHobbyInput('');
    }
  };

  const handleRemoveHobby = (index: number) => {
    setProfile((prev) => ({
      ...prev,
      hobbies: prev.hobbies.filter((_, idx) => idx !== index),
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (saving) return;

    setSaving(true);
    try {
      const resp = await fetch('/api/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...auth.authHeader() },
        body: JSON.stringify({ profile }),
      });

      if (resp.ok) {
        showToast('プロフィールを更新しました！');
        await auth.refreshMe();
      } else {
        showToast('プロフィールの更新に失敗しました');
      }
    } catch (err) {
      console.error(err);
      showToast('エラーが発生しました');
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = () => {
    auth.logout();
    router.replace('/');
  };

  if (loading) {
    return (
      <div className="flex-1 flex justify-center items-center">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col justify-between px-6 pt-8 relative overflow-hidden h-screen bg-[#f5f7fa] text-slate-800">
      {/* Top Background glowing decorations */}
      <div className="absolute top-1/4 left-1/10 w-72 h-72 bg-blue-600/5 rounded-full blur-3xl -z-10" />

      {/* Main Form content (Scrollable) */}
      <div className="flex-1 overflow-y-auto pr-1 pb-6 space-y-6 max-h-[80vh]">
        {/* Title */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-xl font-bold text-slate-800 font-outfit">マイページ</h1>
            <p className="text-[10px] text-slate-500">プロフィールの編集とシステム設定</p>
          </div>
          <button
            onClick={handleLogout}
            className="p-2 rounded-xl bg-rose-50 border border-rose-200 text-rose-600 hover:bg-rose-100 transition-all flex items-center justify-center gap-1 cursor-pointer text-[10px] font-bold shadow-sm"
          >
            <LogOut className="w-3.5 h-3.5" /> ログアウト
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="bg-white border border-gray-200 rounded-2xl p-5 space-y-4 shadow-sm">
            {/* Display Name */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                お名前
              </label>
              <input
                type="text"
                value={profile.display_name}
                onChange={(e) => setProfile({ ...profile, display_name: e.target.value })}
                required
                placeholder="山田 太郎"
                className="w-full px-3 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Birthday and Gender */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                  生年月日
                </label>
                <input
                  type="date"
                  value={profile.birthdate}
                  onChange={handleBirthdateChange}
                  className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                  年齢
                </label>
                <div className="w-full px-3 py-2 bg-gray-100 border border-gray-200 text-xs text-slate-600 rounded-xl min-h-[38px] flex items-center select-none font-mono">
                  {profile.age ? `${profile.age} 歳` : '未入力'}
                </div>
              </div>
            </div>

            {/* Gender and Departure location */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                  性別
                </label>
                <select
                  value={profile.gender}
                  onChange={(e) => setProfile({ ...profile, gender: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-50 border border-gray-200 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded-xl"
                >
                  <option value="" className="bg-white text-slate-800">選択なし</option>
                  <option value="male" className="bg-white text-slate-800">男性</option>
                  <option value="female" className="bg-white text-slate-800">女性</option>
                  <option value="other" className="bg-white text-slate-800">その他</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                  出発地
                </label>
                <input
                  type="text"
                  value={profile.location}
                  onChange={(e) => setProfile({ ...profile, location: e.target.value })}
                  placeholder="例: 東京都"
                  className="w-full px-3 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            {/* Budget */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                ご予算（概算）
              </label>
              <input
                type="text"
                value={profile.budget}
                onChange={(e) => setProfile({ ...profile, budget: e.target.value })}
                placeholder="例: 1回あたり 5万円程度"
                className="w-full px-3 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Hobbies list with Badge tags */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                趣味・関心（Enterで追加、最大10個）
              </label>
              <input
                type="text"
                value={hobbyInput}
                onChange={(e) => setHobbyInput(e.target.value)}
                onKeyDown={handleAddHobby}
                placeholder="例: サウナ、日本酒、アート"
                className="w-full px-3 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-xs text-slate-800 focus:outline-none mb-2"
              />

              <div className="flex flex-wrap gap-1.5">
                {profile.hobbies.map((hobby, index) => (
                  <span
                    key={index}
                    className="bg-blue-50 border border-blue-200 text-blue-600 text-[10px] px-2.5 py-1 rounded-full flex items-center gap-1 font-semibold"
                  >
                    {hobby}
                    <button
                      type="button"
                      onClick={() => handleRemoveHobby(index)}
                      className="hover:text-blue-800"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
                {profile.hobbies.length === 0 && (
                  <span className="text-[10px] text-slate-400 font-bold">趣味タグが登録されていません</span>
                )}
              </div>
            </div>

            {/* Travel Memo / Preference Notes */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                旅行に関するメモ・アレルギーなど
              </label>
              <textarea
                value={profile.notes}
                onChange={(e) => setProfile({ ...profile, notes: e.target.value })}
                rows={3}
                placeholder="例: 移動中の車酔いがあります。人混みが少ない静かな場所を好みます。"
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-xl text-xs text-slate-800 focus:outline-none"
              />
            </div>
          </div>

          {/* Submit */}
          <motion.button
            whileTap={{ scale: 0.98 }}
            type="submit"
            disabled={saving}
            className="w-full py-4 rounded-2xl font-semibold text-white bg-blue-600 hover:bg-blue-700 shadow-md flex items-center justify-center gap-2 cursor-pointer text-sm"
          >
            <Save className="w-4 h-4" />
            {saving ? 'プロフィール更新中...' : 'プロフィールを更新する'}
          </motion.button>
        </form>
      </div>

      {/* Toast Alert */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: 30, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 30, scale: 0.95 }}
            className="absolute bottom-20 left-1/2 -translate-x-1/2 bg-white border border-gray-200 px-4 py-2.5 rounded-xl text-xs font-medium text-slate-800 shadow-xl flex items-center gap-2 z-50 whitespace-nowrap"
          >
            <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-ping" />
            {toast}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Bottom Nav */}
      <BottomNav />
    </div>
  );
}
