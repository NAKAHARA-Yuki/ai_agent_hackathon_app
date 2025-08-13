<script setup>
import { ref, nextTick, computed, onMounted, watch } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useAuthStore } from '@/stores/authStore'

function normalizeName(s) {
  try {
    return String(s || '')
      .trim()
      .replace(/\s+/g, ' ')
      .replace(/[\u3000\s]+/g, ' ')
      .toLowerCase()
  } catch { return String(s || '') }
}

const auth = useAuthStore()

const messages = ref([
  { role: 'assistant', text: 'こんにちは。どんな旅がしたいですか？（例: 美術館めぐり、温泉、自然、グルメ）', citations: [], grounding_html: null }
])
const userInput = ref('')
const isSending = ref(false)
const inputEl = ref(null)
const isComposing = ref(false)
const logEl = ref(null)
const chatEl = ref(null)

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

// 親へイベント: エージェント応答通知・地図オープン
const emit = defineEmits(['agent-update', 'open-map'])

function scrollToBottom() {
  nextTick(() => {
    try {
      const el = chatEl.value || logEl.value
      if (el) el.scrollTop = el.scrollHeight
    } catch {}
  })
}

async function sendMessage() {
  const text = userInput.value.trim()
  if (!text || isSending.value) return
  isSending.value = true
  messages.value.push({ role: 'user', text })
  userInput.value = ''
  await nextTick()
  if (inputEl.value) {
    inputEl.value.style.height = 'auto'
  }
  scrollToBottom()

  // サーバーのエージェントに問い合わせ
  try {
    const resp = await fetch('/api/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...auth.authHeader() },
      body: JSON.stringify({ message: text, user_id: userId.value, session_id: sessionId.value })
    })
    if (!resp.ok) throw new Error('failed')
    const data = await resp.json()
    
  let reply = data.reply || ''
  const citations = data.citations || []
    const groundingHtml = data.grounding_html || null
    let places = Array.isArray(data.places) ? data.places : []
    // 欠損座標の補完（最大20件をサーバーでジオコーディング）
    if (places.length) {
      const needGeocode = places.filter(p => typeof p?.lat !== 'number' || typeof p?.lng !== 'number')
      if (needGeocode.length) {
        try {
          const resp2 = await fetch('/api/geocode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...auth.authHeader() },
            body: JSON.stringify({ names: needGeocode.map(p => p.name).filter(Boolean) })
          })
          if (resp2.ok) {
            const g = await resp2.json()
            const gMap = new Map((g.results || []).map(r => [normalizeName(r.name), r]))
            places = places.map(p => {
              const hit = gMap.get(normalizeName(p.name))
              return (hit && (typeof p.lat !== 'number' || typeof p.lng !== 'number'))
                ? { ...p, lat: hit.lat, lng: hit.lng, note: p.note || hit.formatted_address }
                : p
            })
          }
        } catch (_) { /* noop */ }

        // 依然として欠損がある場合、ブラウザ側で軽量フォールバック（OSM Nominatim）を最大10件だけ試行
        const stillMissing = places.filter(p => typeof p?.lat !== 'number' || typeof p?.lng !== 'number')
        if (stillMissing.length) {
          const names = stillMissing.map(p => p.name).filter(Boolean).slice(0, 10)
          const results = []
          for (const nm of names) {
            try {
              const u = new URL('https://nominatim.openstreetmap.org/search')
              u.searchParams.set('q', nm)
              u.searchParams.set('format', 'json')
              u.searchParams.set('limit', '1')
              u.searchParams.set('addressdetails', '0')
              u.searchParams.set('accept-language', 'ja')
              const r = await fetch(u.toString(), { headers: { 'Accept': 'application/json' } })
              if (r.ok) {
                const arr = await r.json()
                if (Array.isArray(arr) && arr[0]) {
                  const g = arr[0]
                  const lat = g?.lat != null ? Number(g.lat) : undefined
                  const lon = g?.lon != null ? Number(g.lon) : undefined
                  if (Number.isFinite(lat) && Number.isFinite(lon)) {
                    results.push({ name: nm, lat, lng: lon, formatted_address: g.display_name })
                  }
                }
              }
            } catch {}
          }
          if (results.length) {
            const map2 = new Map(results.map(r => [normalizeName(r.name), r]))
            places = places.map(p => {
              const hit = map2.get(normalizeName(p.name))
              return (hit && (typeof p.lat !== 'number' || typeof p.lng !== 'number'))
                ? { ...p, lat: hit.lat, lng: hit.lng, note: p.note || hit.formatted_address }
                : p
            })
          }
        }
      }
    }
    const assistantMessage = { role: 'assistant', text: reply, citations: citations, grounding_html: groundingHtml, places }
    
    if (reply || citations.length > 0 || groundingHtml) {
      messages.value.push(assistantMessage)
    }
    scrollToBottom()

  const routeInfo = data.route_info

  emit('agent-update', { reply, places, route_info: routeInfo, citations })

  } catch (e) {
    console.error('Chat send error', e)
    messages.value.push({ role: 'assistant', text: 'エラーが発生しました。少し待って再試行してください。', citations: [], grounding_html: null })
    scrollToBottom()
  } finally {
    isSending.value = false
  }
}

function onEnter(e) {
  if (e.isComposing || isComposing.value) return
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
    // Allow more tags for grounding results
    return DOMPurify.sanitize(raw, {
      ADD_TAGS: ['svg', 'path', 'circle', 'div', 'g', 'a'],
      ADD_ATTR: ['fill-rule', 'clip-rule', 'd', 'fill', 'class', 'width', 'height', 'viewBox', 'xmlns', 'cx', 'cy', 'r', 'href', 'target', 'rel']
    })
  } catch {
    return text
  }
}

 </script>

<template>
  <div class="chat" ref="chatEl">
    <div class="log" ref="logEl">
      <div v-for="(m, idx) in messages" :key="idx" :class="['msg', m.role]">
        <span v-if="m.role !== 'assistant'" class="bubble">{{ m.text }}</span>
        <div v-else class="bubble">
          <div v-if="m.text" class="text" v-html="renderHtml(m.text)"></div>
          <div v-if="m.citations && m.citations.length" class="citations">
            <p><strong>引用元:</strong></p>
            <ul>
              <li v-for="c in m.citations" :key="c.index">
                [{{ c.index }}] <a :href="c.uri" target="_blank" rel="noopener">{{ c.title }}</a>
              </li>
            </ul>
          </div>
          <div v-if="m.grounding_html" class="grounding" v-html="m.grounding_html"></div>
          <div v-if="m.places && m.places.length" class="places">
            <p><strong>場所:</strong></p>
            <ul>
              <li v-for="(p, i) in m.places" :key="i">
                {{ p.name || p.title }}
                <small v-if="p.note" style="color:#6b7280;"> — {{ p.note }}</small>
              </li>
            </ul>
          </div>
        </div>
      </div>
      <!-- タイピング中インジケーター -->
      <div v-if="isSending" class="msg assistant">
        <span class="bubble typing" aria-live="polite" aria-label="応答を待機中">
          <span class="dot"></span><span class="dot"></span><span class="dot"></span>
        </span>
      </div>
    </div>
    
    <div class="composer-area">
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
        <button type="submit" :disabled="isSending" aria-label="送信">
          <svg v-if="!isSending" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
          <svg v-else class="spinner" width="18" height="18" viewBox="0 0 50 50" aria-hidden="true">
            <circle class="path" cx="25" cy="25" r="20" fill="none" stroke-width="4" stroke-linecap="round" />
          </svg>
        </button>
      </form>
      <div class="composer-actions">
        <button type="button" class="map-open-btn" @click="emit('open-map')" aria-label="地図を表示">🗺️ 地図を表示</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat { display:flex; flex-direction:column; width:100%; overflow:auto; -webkit-overflow-scrolling: touch; overscroll-behavior: contain; min-height: 0; }
.log { flex:1; overflow: visible; padding: 8px 12px; display:flex; flex-direction:column; gap:8px; }
.msg { display:flex; }
.msg.user { justify-content:flex-end; }
.bubble { background:#f3f4f6; padding:10px 12px; border-radius: 10px; max-width: 80%; }
.msg.user .bubble { background:#2d7ef7; color:#fff; }
.bubble :where(h1,h2,h3){ margin: 0.4em 0 0.3em; font-weight:600; }
.bubble :where(p){ margin: 0.3em 0; }
.bubble :where(ul,ol){ padding-left: 1.2em; margin: 0.3em 0; }
.bubble :where(code){ background: rgba(0,0,0,0.06); padding: 0.1em 0.3em; border-radius: 4px; }
.bubble :where(pre){ background: #0f172a; color:#e2e8f0; padding: 8px; border-radius: 6px; overflow:auto; }
.grounding { margin-bottom: 8px; }
.citations { margin-top: 12px; padding-top: 8px; border-top: 1px solid #e5e7eb; font-size: 0.9em; color: #6b7280; }
.citations p { margin: 0 0 4px; }
.citations ul { margin: 0; padding-left: 18px; }
.places { margin-top: 8px; padding-top: 6px; border-top: 1px dashed #e5e7eb; font-size: 0.95em; }
.bubble.typing { display:inline-flex; align-items:center; gap:6px; }
.bubble.typing .dot { width:6px; height:6px; border-radius:50%; background:#9ca3af; display:inline-block; animation: typingBlink 1.2s infinite ease-in-out; }
.bubble.typing .dot:nth-child(2) { animation-delay: .2s; }
.bubble.typing .dot:nth-child(3) { animation-delay: .4s; }
@keyframes typingBlink { 0%, 80%, 100% { opacity: .3; transform: translateY(0); } 40% { opacity: 1; transform: translateY(-2px); } }
.composer-area { position: static; background:#fff; border-top:1px solid #eee; padding: 6px 0; box-shadow: 0 -2px 8px rgba(0,0,0,0.05); }
.composer { --composer-h: 44px; display:flex; gap:8px; align-items:stretch; background:#fff; width: 100%; padding: 6px 12px; box-sizing: border-box; }
/* 入力欄と送信ボタンの高さを統一 */
.composer textarea { flex: 1 1 0%; min-width: 0; padding:10px 12px; border-radius:12px; border:1px solid #e5e7eb; font-size:15px; line-height:1.4; resize: none; height: auto; min-height: var(--composer-h); max-height: 160px; box-sizing: border-box; }
.composer textarea:disabled { background: #f9fafb; cursor: not-allowed; }
.composer button { flex: 0 0 auto; width: var(--composer-h); height: auto; min-height: var(--composer-h); align-self: stretch; display:grid; place-items:center; background:#111827; color:#fff; border:none; border-radius:12px; font-weight:600; padding: 0; }
.composer button[disabled] { opacity: 0.7; cursor: not-allowed; }
.composer button .spinner { animation: rot 1s linear infinite; }
.composer button .spinner .path { stroke: #fff; stroke-dasharray: 90, 150; stroke-dashoffset: 0; animation: dash 1.2s ease-in-out infinite; }
@keyframes rot { 100% { transform: rotate(360deg); } }
@keyframes dash { 0% { stroke-dasharray: 1, 200; stroke-dashoffset: 0; } 50% { stroke-dasharray: 90, 150; stroke-dashoffset: -40px; } 100% { stroke-dasharray: 90, 150; stroke-dashoffset: -120px; } }

.composer-actions { margin-top: 6px; display: none; padding: 0 12px; box-sizing: border-box; }
.map-open-btn { width: 100%; background:#111827; color:#fff; border:none; border-radius:10px; padding:10px; font-weight:700; }

@media (max-width: 600px) {
  /* モバイルではコンポーザー一式を下部にピン留め */
  .composer-area { position: sticky; bottom: 0; z-index: 5; box-shadow: 0 -6px 12px rgba(0,0,0,0.05); padding-bottom: calc(6px + env(safe-area-inset-bottom)); }
  .composer-actions { display: block; }
  .log { padding-bottom: calc(120px + env(safe-area-inset-bottom)); }
  /* ボタンはコンパクトに */
  .composer { --composer-h: 42px; }
}

/* タブレット幅でも右ペインのマップは非表示のため、地図ボタンを出す */
@media (max-width: 960px) {
  .composer-area { position: sticky; bottom: 0; z-index: 5; box-shadow: 0 -6px 12px rgba(0,0,0,0.05); padding-bottom: calc(6px + env(safe-area-inset-bottom)); }
  .composer-actions { display: block; }
  .log { padding-bottom: calc(120px + env(safe-area-inset-bottom)); }
}
</style>
