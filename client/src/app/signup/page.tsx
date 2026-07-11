'use client';

import React, { useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useAuthStore, USER_ID_REGEX } from '@/stores/authStore';
import { motion } from 'framer-motion';
import { appPath } from '@/utils/pathHelper';

function SignupContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const auth = useAuthStore();

  const [name, setName] = useState('');
  const [userId, setUserId] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const redirect = searchParams.get('redirect');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setError('');
      setLoading(true);

      if (!USER_ID_REGEX.test(userId)) {
        throw new Error('ユーザーIDは英小文字・数字・_・-で3〜30文字にしてください');
      }
      if (password.length < 8) {
        throw new Error('パスワードは8文字以上にしてください');
      }

      await auth.signup({ name, user_id: userId, password });
      
      if (redirect) {
        router.replace(appPath(redirect));
      } else {
        router.replace(appPath('/'));
      }
    } catch (e: any) {
      setError(e?.message || '登録に失敗しました');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col justify-center px-6 py-12 relative overflow-hidden">
      {/* Background glowing decorations */}
      <div className="absolute top-1/4 right-1/10 w-64 h-64 bg-purple-600/20 rounded-full blur-3xl -z-10" />
      <div className="absolute bottom-1/4 left-1/10 w-72 h-72 bg-blue-600/10 rounded-full blur-3xl -z-10" />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        className="w-full glass-panel rounded-2xl p-8 shadow-2xl relative"
      >
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold tracking-tight text-white mb-2 font-outfit">
            新規登録
          </h1>
          <p className="text-sm text-slate-400">
            アカウントを作成して、AIと一緒に旅スタイルを見つけましょう。
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-400 block">
              お名前
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例: 山田 太郎"
              required
              className="w-full px-4 py-3 glass-input text-white focus:outline-none text-sm"
            />
          </div>

          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-400 block">
              ユーザーID
            </label>
            <input
              type="text"
              value={userId}
              onChange={(e) => setUserId(e.target.value.trim())}
              placeholder="例: gemini_user"
              required
              className="w-full px-4 py-3 glass-input text-white focus:outline-none text-sm"
              autoComplete="username"
            />
            <p className="text-[10px] text-slate-500">
              英小文字・数字・アンダースコア(_)、ハイフン(-)の3〜30文字。
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-400 block">
              パスワード
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              className="w-full px-4 py-3 glass-input text-white focus:outline-none text-sm"
              autoComplete="new-password"
            />
            <p className="text-[11px] text-slate-500">
              パスワードは8文字以上である必要があります。
            </p>
          </div>

          {error && (
            <motion.p
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="text-xs font-medium text-rose-400 bg-rose-950/30 border border-rose-900/40 rounded-lg px-3 py-2"
            >
              {error}
            </motion.p>
          )}

          <motion.button
            whileTap={{ scale: 0.98 }}
            type="submit"
            disabled={loading}
            className="w-full py-3.5 rounded-xl text-sm font-semibold text-white animated-gradient shadow-lg hover:shadow-indigo-500/10 transition-all flex justify-center items-center cursor-pointer"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                登録中...
              </span>
            ) : (
              '登録してはじめる'
            )}
          </motion.button>
        </form>

        <div className="mt-8 text-center border-t border-white/5 pt-6">
          <p className="text-xs text-slate-400">
            すでにアカウントをお持ちですか？{' '}
            <Link
              href={`/login${searchParams.toString() ? '?' + searchParams.toString() : ''}`}
              className="text-indigo-400 font-semibold hover:text-indigo-300 transition-colors"
            >
              ログインする
            </Link>
          </p>
        </div>
      </motion.div>
    </div>
  );
}

export default function SignupPage() {
  return (
    <Suspense fallback={
      <div className="flex-1 flex justify-center items-center">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-indigo-500"></div>
      </div>
    }>
      <SignupContent />
    </Suspense>
  );
}
