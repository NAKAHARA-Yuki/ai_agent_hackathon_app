<script setup>
import { ref, nextTick, computed, onMounted, watch } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useAuthStore } from '@/stores/authStore'

const auth = useAuthStore()

const messages = ref([
  { role: 'assistant', text: 'こんにちは。どんな旅がしたいですか？（例: 美術館めぐり、温泉、自然、グルメ）' }
])
const userInput = ref('')
const isSending = ref(false)
const inputEl = ref(null)
const isComposing = ref(false)

// セッションIDはページライフサイクル内でのみ保持（リロードで新規発行）
const userId = computed(() => auth.user?.id || 'u_local')
const sessionId = ref('')

function newUUID() {
  return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function ensureSessionId(reset = false) {
  if (reset || !sessionId.value) {
    sessionId.value = newUUID()
    console.debug('[Chat] new session id generated', { user_id: userId.value, session_id: sessionId.value })
  }
}

onMounted(() => {
  ensureSessionId(true)
})

watch(userId, () => {
  // ユーザーが切り替わったら新しいセッションにする
  ensureSessionId(true)
})

// 親へ: エージェント応答に含まれる場所候補を通知
const emit = defineEmits(['agent-update'])

async function sendMessage() {
  const text = userInput.value.trim()
  if (!text || isSending.value) return
  isSending.value = true
  console.debug('[Chat] send start', { user_id: userId.value, session_id: sessionId.value, len: text.length })
  messages.value.push({ role: 'user', text })
  userInput.value = ''
  await nextTick()
  if (inputEl.value) {
    inputEl.value.style.height = 'auto'
  }

  // サーバーのエージェントに問い合わせ（簡易プロトタイプ）
  try {
    const resp = await fetch('/api/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...auth.authHeader() },
      body: JSON.stringify({ message: text, user_id: userId.value, session_id: sessionId.value })
    })
    if (!resp.ok) throw new Error('failed')
  const data = await resp.json()
  console.debug('[Chat] response', { ok: true, keys: Object.keys(data || {}), hasPlaces: Array.isArray(data?.places) })
  const reply = data.reply || '提案を取得できませんでした。'
  messages.value.push({ role: 'assistant', text: reply })
  const routeInfo = Array.isArray(data.route_info) ? data.route_info : undefined

    // 場所候補: [{ name, lat, lng, note }]
    if (Array.isArray(data.places)) {
      let places = data.places
      const needGeocode = places.filter(p => typeof p?.lat !== 'number' || typeof p?.lng !== 'number')
      if (needGeocode.length) {
        try {
          const resp2 = await fetch('/api/geocode', {
            method: 'POST', headers: { 'Content-Type': 'application/json', ...auth.authHeader() },
            body: JSON.stringify({ names: needGeocode.map(p => p.name).filter(Boolean) })
          })
          if (resp2.ok) {
            const g = await resp2.json()
            const map = new Map((g.results || []).map(r => [r.name, r]))
            places = places.map(p => {
              const hit = map.get(p.name)
              return (hit && (typeof p.lat !== 'number' || typeof p.lng !== 'number'))
                ? { ...p, lat: hit.lat, lng: hit.lng, note: p.note || hit.formatted_address }
                : p
            })
          }
        } catch (_) { /* noop */ }
      }
  console.debug('[Chat] places processed', { count: places.length })
  emit('agent-update', { reply, places, route_info: routeInfo })
    } else {
  emit('agent-update', { reply, route_info: routeInfo })
    }
  } catch (e) {
    console.debug('[Chat] error', e)
    messages.value.push({ role: 'assistant', text: 'エラーが発生しました。少し待って再試行してください。' })
  } finally {
    console.debug('[Chat] send end')
    isSending.value = false
  }
}

function onEnter(e) {
  // IME 変換中は送信しない（Enterは変換確定用）
  if (e.isComposing || isComposing.value) return
  // Shift+Enter で改行、Enterのみで送信
  if (e.shiftKey) return
  e.preventDefault()
  sendMessage()
}

function autoResize(e) {
  const el = e.target
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
}

function renderHtml(text) {
  try {
    const raw = marked.parse(text || '')
    return DOMPurify.sanitize(raw)
  } catch {
    return text
  }
}
</script>

<template>
  <div class="chat">
    <div class="log">
      <div v-for="(m, idx) in messages" :key="idx" :class="['msg', m.role]">
  <span v-if="m.role !== 'assistant'" class="bubble">{{ m.text }}</span>
  <span v-else class="bubble" v-html="renderHtml(m.text)"></span>
      </div>
    </div>
    <form class="composer" @submit.prevent="sendMessage">
      <textarea
        ref="inputEl"
        v-model="userInput"
        rows="1"
        placeholder="行きたい雰囲気や目的を自由に入力..."
        @keydown.enter="onEnter"
  @compositionstart="isComposing = true"
  @compositionend="isComposing = false"
        @input="autoResize"
        :disabled="isSending"
      />
      <button type="submit" :disabled="isSending">{{ isSending ? '送信中…' : '送信' }}</button>
    </form>
  </div>
</template>

<style scoped>
.chat { display:flex; flex-direction:column; width:100%; }
.log { flex:1; overflow:auto; padding: 12px; display:flex; flex-direction:column; gap:8px; }
.msg { display:flex; }
.msg.user { justify-content:flex-end; }
.bubble { background:#f3f4f6; padding:10px 12px; border-radius: 10px; max-width: 80%; }
.msg.user .bubble { background:#2d7ef7; color:#fff; }
.bubble :where(h1,h2,h3){ margin: 0.4em 0 0.3em; font-weight:600; }
.bubble :where(p){ margin: 0.3em 0; }
.bubble :where(ul,ol){ padding-left: 1.2em; margin: 0.3em 0; }
.bubble :where(code){ background: rgba(0,0,0,0.06); padding: 0.1em 0.3em; border-radius: 4px; }
.bubble :where(pre){ background: #0f172a; color:#e2e8f0; padding: 8px; border-radius: 6px; overflow:auto; }
.composer { display:flex; gap:8px; border-top:1px solid #eee; padding:12px; align-items:stretch; background:#fff; }
/* 入力欄: 広め、送信ボタン: 固定幅で比率を安定化（約85:15想定） */
.composer textarea { flex: 1 1 auto; min-width: 0; padding:10px 12px; border-radius:8px; border:1px solid #e5e7eb; font-size:14px; line-height:1.4; resize: none; height: 40px; max-height: 160px; }
.composer textarea:disabled { background: #f9fafb; cursor: not-allowed; }
.composer button { flex: 0 0 112px; height: auto; align-self: stretch; display:flex; align-items:center; justify-content:center; background:#2d7ef7; color:#fff; border:none; border-radius:8px; font-weight:600; min-height: 40px; }
.composer button[disabled] { opacity: 0.6; cursor: not-allowed; }

@media (max-width: 600px) {
  /* モバイルではコンポーザーを下部にピン留め */
  .composer { position: sticky; bottom: 0; z-index: 5; box-shadow: 0 -6px 12px rgba(0,0,0,0.05); }
  .log { padding-bottom: 72px; }
  /* ボタン幅を少し小さくする（約80:20） */
  .composer button { flex-basis: 96px; }
}
</style>
