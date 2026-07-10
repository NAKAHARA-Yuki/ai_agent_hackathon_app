import { create } from 'zustand';

const STORAGE_KEY = 'travelquiz:auth';

export interface User {
  user_id: string;
  name: string;
  diagnosis_completed: boolean;
  [key: string]: any;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (credentials: { user_id: string; password: string }) => Promise<void>;
  signup: (userData: { name: string; user_id: string; password: string }) => Promise<void>;
  logout: (reason?: string | null) => void;
  refreshMe: () => Promise<User | null>;
  checkAndCleanExpiredToken: () => boolean;
  getTokenTimeRemaining: () => number;
  authHeader: () => Record<string, string>;
}

// ユーザーIDのバリデーション正規表現
export const USER_ID_REGEX = /^[a-z0-9_-]{3,30}$/;

function loadAuth() {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveAuth(payload: any) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

function clearAuth() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(STORAGE_KEY);
}

function parseJwtPayload(tokenStr: string | null): any {
  if (!tokenStr) return null;
  try {
    const parts = tokenStr.split('.');
    if (parts.length !== 3) return null;
    return JSON.parse(atob(parts[1]));
  } catch (error) {
    console.warn('Token parsing failed:', error);
    return null;
  }
}

function isTokenExpired(token: string | null): boolean {
  const payload = parseJwtPayload(token);
  if (!payload || typeof payload.exp !== 'number') return true;
  const now = Math.floor(Date.now() / 1000);
  return now >= payload.exp;
}

export const useAuthStore = create<AuthState>((set, get) => {
  const initialAuth = loadAuth();
  const token = initialAuth?.token || null;
  const user = initialAuth?.user || null;
  const isAuthenticated = !!token && !isTokenExpired(token);

  async function requestJSON<T>(
    url: string,
    options: RequestInit = {},
    { timeoutMs = 15000 } = {}
  ): Promise<T> {
    if (get().checkAndCleanExpiredToken()) {
      throw new Error('セッションの有効期限が切れています。再度ログインしてください。');
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const resp = await fetch(url, { ...options, signal: controller.signal });
      const ct = resp.headers.get('content-type') || '';
      const isJSON = ct.includes('application/json');

      if (!resp.ok) {
        if (resp.status === 401) {
          get().logout('expired');
          throw new Error('認証の有効期限が切れました。再度ログインしてください。');
        }

        let message = resp.statusText || 'リクエストに失敗しました';
        try {
          if (isJSON) {
            const data = await resp.json();
            message = data?.error || message;
          } else {
            const text = await resp.text();
            if (text && typeof text === 'string') {
              if (/Service Unavailable/i.test(text)) {
                message = 'サービスが一時的に利用できません (503)';
              } else {
                message = `${message} (${resp.status})`;
              }
            }
          }
        } catch {}
        throw new Error(message);
      }

      if (isJSON) {
        return (await resp.json()) as T;
      }
      return null as T;
    } catch (e: any) {
      if (e?.name === 'AbortError') {
        throw new Error('タイムアウトしました。しばらくしてから再試行してください。');
      }
      throw new Error(e?.message || '通信中にエラーが発生しました');
    } finally {
      clearTimeout(timer);
    }
  }

  return {
    user,
    token,
    isAuthenticated,

    authHeader(): Record<string, string> {
      const currentToken = get().token;
      return currentToken ? { Authorization: `Bearer ${currentToken}` } : {};
    },

    getTokenTimeRemaining() {
      const currentToken = get().token;
      const payload = parseJwtPayload(currentToken);
      if (!payload || typeof payload.exp !== 'number') return 0;
      const now = Math.floor(Date.now() / 1000);
      return Math.max(0, payload.exp - now);
    },

    checkAndCleanExpiredToken() {
      const currentToken = get().token;
      if (currentToken && isTokenExpired(currentToken)) {
        get().logout('expired');
        return true;
      }
      return false;
    },

    async signup({ name, user_id, password }) {
      if (!name || !user_id || !password) throw new Error('必須項目が未入力です');
      if (!USER_ID_REGEX.test(user_id)) {
        throw new Error('ユーザーIDは英小文字・数字・_・-で3〜30文字');
      }
      if (password.length < 8) throw new Error('パスワードは8文字以上にしてください');

      const data = await requestJSON<{ user: User; token: string }>('/api/auth/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, user_id, password }),
      });

      if (!data) throw new Error('登録に失敗しました');
      const payload = { user: data.user, token: data.token, ts: Date.now() };
      saveAuth(payload);

      set({
        user: data.user,
        token: data.token,
        isAuthenticated: true,
      });
    },

    async login({ user_id, password }) {
      if (!user_id || !password) throw new Error('ユーザーIDとパスワードを入力してください');
      if (!USER_ID_REGEX.test(user_id)) {
        throw new Error('ユーザーIDは英小文字・数字・_・-で3〜30文字');
      }

      const data = await requestJSON<{ user: User; token: string }>('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id, password }),
      });

      if (!data) throw new Error('ログインに失敗しました');
      const payload = { user: data.user, token: data.token, ts: Date.now() };
      saveAuth(payload);

      set({
        user: data.user,
        token: data.token,
        isAuthenticated: true,
      });
    },

    async refreshMe() {
      const currentToken = get().token;
      if (!currentToken) return null;
      try {
        const resp = await fetch('/api/me', { headers: { ...get().authHeader() } });
        if (resp.ok) {
          const me = await resp.json();
          const merged = { ...(get().user || {}), ...me } as User;
          const payload = { user: merged, token: currentToken, ts: Date.now() };
          saveAuth(payload);

          set({
            user: merged,
          });
          return merged;
        }
      } catch {}
      return null;
    },

    logout(reason = null) {
      clearAuth();
      set({
        user: null,
        token: null,
        isAuthenticated: false,
      });

      if (reason === 'expired') {
        setTimeout(() => {
          console.info('セッションの有効期限が切れました。再度ログインしてください。');
          if (typeof window !== 'undefined') {
            const currentPath = window.location.pathname;
            if (currentPath !== '/login' && currentPath !== '/signup') {
              window.dispatchEvent(
                new CustomEvent('auth:expired', { detail: { redirect: currentPath } })
              );
            }
          }
        }, 100);
      }
    },
  };
});
