import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { USER_ID_REGEX } from '../constants/validation'

const STORAGE_KEY = 'travelquiz:auth'

function loadAuth() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function saveAuth(payload) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
}

function clearAuth() {
  localStorage.removeItem(STORAGE_KEY)
}

export const useAuthStore = defineStore('auth', () => {
  const state = ref(loadAuth())

  const user = computed(() => state.value?.user || null)
  const token = computed(() => state.value?.token || null)
  const isAuthenticated = computed(() => !!token.value && !isTokenExpired())

  // JWT トークンの有効期限をチェック
  function isTokenExpired() {
    if (!token.value) return true
    
    try {
      // JWT のペイロード部分をデコード（base64）
      const payload = JSON.parse(atob(token.value.split('.')[1]))
      const exp = payload.exp
      
      if (!exp) return true
      
      // 現在時刻と比較（expは秒単位、Date.now()はミリ秒単位）
      const now = Math.floor(Date.now() / 1000)
      return now >= exp
    } catch (error) {
      console.warn('Token parsing failed:', error)
      return true
    }
  }

  // トークンの残り時間（秒）を取得
  function getTokenTimeRemaining() {
    if (!token.value) return 0
    
    try {
      const payload = JSON.parse(atob(token.value.split('.')[1]))
      const exp = payload.exp
      
      if (!exp) return 0
      
      const now = Math.floor(Date.now() / 1000)
      return Math.max(0, exp - now)
    } catch (error) {
      return 0
    }
  }

  // 内部: タイムアウト付きのJSONリクエスト。非JSONレスポンス(HTMLなど)も分かりやすく扱う
  async function requestJSON(url, options = {}, { timeoutMs = 15000 } = {}) {
    // 事前にトークンの有効性をチェック
    if (checkAndCleanExpiredToken()) {
      throw new Error('セッションの有効期限が切れています。再度ログインしてください。')
    }

    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    try {
      const resp = await fetch(url, { ...options, signal: controller.signal })
      const ct = resp.headers.get('content-type') || ''
      const isJSON = ct.includes('application/json')

      if (!resp.ok) {
        // 401 Unauthorized の場合は認証エラーとして処理
        if (resp.status === 401) {
          logout('expired')
          throw new Error('認証の有効期限が切れました。再度ログインしてください。')
        }

        // エラー応答: JSONならerrorメッセージ、非JSONならテキストから要約
        let message = resp.statusText || 'リクエストに失敗しました'
        try {
          if (isJSON) {
            const data = await resp.json()
            message = data?.error || message
          } else {
            const text = await resp.text()
            if (text && typeof text === 'string') {
              // Cloud Run等の"Service Unavailable"を優先的に整形
              if (/Service Unavailable/i.test(text)) {
                message = 'サービスが一時的に利用できません (503)'
              } else {
                // 先頭100文字程度を要約
                message = `${message} (${resp.status})`
              }
            }
          }
        } catch {
          // JSONパースやテキスト取得に失敗しても既定のメッセージで返す
        }
        throw new Error(message)
      }

      if (isJSON) {
        return await resp.json()
      }
      // JSON以外(204等)は空を返す
      return null
    } catch (e) {
      if (e?.name === 'AbortError') {
        throw new Error('タイムアウトしました。しばらくしてから再試行してください。')
      }
      // ネットワーク/パース例外も統一的に扱う
      throw new Error(e?.message || '通信中にエラーが発生しました')
    } finally {
      clearTimeout(timer)
    }
  }

  async function signup({ name, user_id, password }) {
    if (!name || !user_id || !password) throw new Error('必須項目が未入力です')
    if (!USER_ID_REGEX.test(user_id)) throw new Error('ユーザーIDは英小文字・数字・_・-で3〜30文字')
    if (password.length < 8) throw new Error('パスワードは8文字以上にしてください')
    const data = await requestJSON('/api/auth/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, user_id, password })
    })
    if (!data) throw new Error('登録に失敗しました')
  const payload = { user: data.user, token: data.token, ts: Date.now() }
    saveAuth(payload)
    state.value = payload
  }

  async function login({ user_id, password }) {
    if (!user_id || !password) throw new Error('ユーザーIDとパスワードを入力してください')
    if (!USER_ID_REGEX.test(user_id)) throw new Error('ユーザーIDは英小文字・数字・_・-で3〜30文字')
    const data = await requestJSON('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id, password })
    })
    if (!data) throw new Error('ログインに失敗しました')
  const payload = { user: data.user, token: data.token, ts: Date.now() }
    saveAuth(payload)
    state.value = payload
  }

  function authHeader() {
    return token.value ? { Authorization: `Bearer ${token.value}` } : {}
  }

  async function refreshMe() {
    if (!token.value) return null
    try {
      const resp = await fetch('/api/me', { headers: { ...authHeader() } })
      if (resp.ok) {
        const me = await resp.json()
        const merged = { ...(state.value?.user || {}), ...me }
        const payload = { user: merged, token: token.value, ts: Date.now() }
        saveAuth(payload)
        state.value = payload
        return merged
      }
    } catch {}
    return null
  }

  function logout(reason = null) {
    clearAuth()
    state.value = null
    
    // セッション切れの場合はメッセージを表示
    if (reason === 'expired') {
      // Vue Router の外部からナビゲーションする場合に備えて、次のティックで実行
      setTimeout(() => {
        // トースト通知などがあれば表示、なければconsoleに記録
        console.info('セッションの有効期限が切れました。再度ログインしてください。')
        
        // ログインページに遷移（現在のページを remember）
        const currentPath = window.location.pathname
        if (currentPath !== '/login' && currentPath !== '/signup') {
          window.location.href = `/login?redirect=${encodeURIComponent(currentPath)}`
        }
      }, 100)
    }
  }

  // 期限切れトークンの自動クリーンアップ
  function checkAndCleanExpiredToken() {
    if (token.value && isTokenExpired()) {
      logout('expired')
      return true
    }
    return false
  }

  return { 
    user, 
    token, 
    isAuthenticated, 
    signup, 
    login, 
    logout, 
    authHeader, 
    refreshMe,
    isTokenExpired,
    getTokenTimeRemaining,
    checkAndCleanExpiredToken
  }
})
