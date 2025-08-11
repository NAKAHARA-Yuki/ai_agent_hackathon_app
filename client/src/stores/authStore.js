import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

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
  const isAuthenticated = computed(() => !!token.value)

  async function signup({ name, user_id, password }) {
    if (!name || !user_id || !password) throw new Error('必須項目が未入力です')
    if (!/^[a-z0-9_-]{3,30}$/.test(user_id)) throw new Error('ユーザーIDは英小文字・数字・_・-で3〜30文字')
    if (password.length < 8) throw new Error('パスワードは8文字以上にしてください')
    const resp = await fetch('/api/auth/signup', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, user_id, password })
    })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data?.error || '登録に失敗しました')
    const payload = { user: data.user, token: data.token, ts: Date.now() }
    saveAuth(payload)
    state.value = payload
  }

  async function login({ user_id, password }) {
    if (!user_id || !password) throw new Error('ユーザーIDとパスワードを入力してください')
    const resp = await fetch('/api/auth/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id, password })
    })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data?.error || 'ログインに失敗しました')
    const payload = { user: data.user, token: data.token, ts: Date.now() }
    saveAuth(payload)
    state.value = payload
  }

  function authHeader() {
    return token.value ? { Authorization: `Bearer ${token.value}` } : {}
  }

  function logout() {
    clearAuth()
    state.value = null
  }

  return { user, token, isAuthenticated, signup, login, logout, authHeader }
})
