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
// メッセージDOM参照（表抽出や画像化に利用）
const msgEls = ref({})
function setMsgRef(idx, el) { if (el) msgEls.value[idx] = el }

// 表の状態管理（大きい表は既定で折り畳み）
const tableStates = ref({}) // { [idx]: { collapsed: boolean, hasTable: boolean } }
// スケジュール表示モード
const scheduleStates = ref({}) // { [idx]: { found: boolean, mode: 'accordion'|'table' } }

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
    const assistantMessage = { role: 'assistant', text: reply, citations: citations, grounding_html: groundingHtml, places }
    
  if (reply || citations.length > 0 || groundingHtml) {
      messages.value.push(assistantMessage)
      // 表の有無/大きさに応じて初期状態セット
      try {
        const html = renderHtml(reply || '')
        const idx = messages.value.length - 1
        ensureTableState(idx, html)
    // 次tickでDOM構築後にアコーディオン生成
    nextTick(() => enhanceScheduleTables(idx))
      } catch {}
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
    // Enable GFM (tables, strikethrough, task lists) and soft line breaks
    marked.setOptions({ gfm: true, breaks: true, headerIds: false, mangle: false })
    const raw = marked.parse(text || '')
    // Allow table and related tags for nicer markdown tables
    return DOMPurify.sanitize(raw, {
      ADD_TAGS: ['svg', 'path', 'circle', 'div', 'g', 'a', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'caption', 'details', 'summary', 'span', 'section', 'dl', 'dt', 'dd'],
      ADD_ATTR: [
        'fill-rule', 'clip-rule', 'd', 'fill', 'class', 'width', 'height', 'viewBox', 'xmlns', 'cx', 'cy', 'r', 'href', 'target', 'rel',
        'colspan', 'rowspan', 'align', 'scope'
      ]
    })
  } catch {
    return text
  }
}

function hasTableInHtml(html) {
  try {
    const div = document.createElement('div')
    div.innerHTML = html || ''
    return !!div.querySelector('table')
  } catch { return false }
}

function isLargeTableInHtml(html, rowThr = 12, colThr = 6) {
  try {
    const div = document.createElement('div')
    div.innerHTML = html || ''
    const tbl = div.querySelector('table')
    if (!tbl) return false
    const rows = tbl.querySelectorAll('tr').length
    const firstRow = tbl.querySelector('tr')
    const cols = firstRow ? firstRow.querySelectorAll('th,td').length : 0
    return rows > rowThr || cols > colThr
  } catch { return false }
}

function ensureTableState(idx, html) {
  const st = tableStates.value[idx]
  if (st && typeof st.collapsed === 'boolean') return st
  const hasTbl = hasTableInHtml(html)
  const large = hasTbl && isLargeTableInHtml(html)
  const next = { collapsed: !!large, hasTable: !!hasTbl }
  tableStates.value = { ...tableStates.value, [idx]: next }
  return next
}

function toggleTableCollapse(idx) {
  const st = tableStates.value[idx] || { collapsed: false, hasTable: false }
  tableStates.value = { ...tableStates.value, [idx]: { ...st, collapsed: !st.collapsed } }
}

async function exportTableAsCSV(idx) {
  try {
    const root = msgEls.value[idx]
    if (!root) return
    const tbl = root.querySelector('table')
    if (!tbl) return
    const rows = Array.from(tbl.querySelectorAll('tr'))
    const csv = rows.map(tr => {
      const cells = Array.from(tr.querySelectorAll('th,td')).map(td => {
        const t = (td.textContent || '').replace(/\r?\n|\r/g, ' ').trim()
        const esc = t.replace(/"/g, '""')
        if (/[",\n]/.test(esc)) return `"${esc}"`
        return esc
      })
      return cells.join(',')
    }).join('\n')
    const bom = '\ufeff'
    const blob = new Blob([bom + csv], { type: 'text/csv;charset=utf-8;' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `table-${idx + 1}.csv`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  } catch (e) { console.error('CSV export failed', e) }
}

async function exportTableAsImage(idx) {
  try {
    const root = msgEls.value[idx]
    if (!root) return
    const tbl = root.querySelector('table')
    if (!tbl) return
    const { default: html2canvas } = await import('html2canvas')
    // 一時的に折り畳み解除して全体を撮影
    const st = tableStates.value[idx] || { collapsed: false }
    const wasCollapsed = !!st.collapsed
    if (wasCollapsed) toggleTableCollapse(idx)
    // スケジュール表示がアコーディオンなら一時的にテーブル表示へ
    const sch = scheduleStates.value[idx]
    const wasAccordion = sch && sch.mode === 'accordion'
    if (wasAccordion) switchScheduleView(idx, 'table')
    await nextTick()
    const canvas = await html2canvas(tbl, { backgroundColor: '#ffffff', scale: 2, useCORS: true })
    const url = canvas.toDataURL('image/png')
    const a = document.createElement('a')
    a.href = url
    a.download = `table-${idx + 1}.png`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    if (wasAccordion) switchScheduleView(idx, 'accordion')
    if (wasCollapsed) { toggleTableCollapse(idx); await nextTick() }
  } catch (e) { console.error('Image export failed', e) }
}

function isScheduleTable(tableEl) {
  try {
    const ths = Array.from(tableEl.querySelectorAll('thead th, tr:first-child th, tr:first-child td')).map(x => (x.textContent || '').trim())
    const hasTime = ths.some(t => /時間|時刻|time/i.test(t))
    const hasPlan = ths.some(t => /予定|プラン|行程|title|内容/i.test(t))
    return hasTime && hasPlan
  } catch { return false }
}

function buildAccordionFromTable(tableEl) {
  const container = document.createElement('div')
  container.className = 'accordion-block'
  const rows = Array.from(tableEl.querySelectorAll('tr'))
  if (!rows.length) return container
  // header
  const headers = Array.from(rows[0].querySelectorAll('th,td')).map(x => (x.textContent || '').trim())
  const idxIcon = headers.findIndex(h => /アイコン|icon|emoji/i.test(h))
  const idxTime = headers.findIndex(h => /時間|時刻|time/i.test(h))
  const idxTitle = headers.findIndex(h => /予定|プラン|行程|title|内容/i.test(h))
  const idxDetail = headers.findIndex(h => /詳細|detail|説明/i.test(h))
  // data rows
  for (let i = 1; i < rows.length; i++) {
    const cells = Array.from(rows[i].querySelectorAll('th,td'))
    const get = (idx) => (idx >= 0 && cells[idx]) ? (cells[idx].textContent || '').trim() : ''
    const icon = get(idxIcon) || '•'
    const time = get(idxTime)
    const title = get(idxTitle)
    const detail = get(idxDetail)
    const otherPairs = []
    headers.forEach((h, j) => {
      if (![idxIcon, idxTime, idxTitle, idxDetail].includes(j) && (cells[j] && (cells[j].textContent || '').trim())) {
        otherPairs.push([h, (cells[j].textContent || '').trim()])
      }
    })
    const detailsEl = document.createElement('details')
    const summaryEl = document.createElement('summary')
    summaryEl.innerHTML = `<span class="it-icon">${icon}</span><span class="it-time">${time}</span><span class="it-title">${title}</span>`
    const bodyEl = document.createElement('div')
    bodyEl.className = 'it-body'
    if (detail) {
      const p = document.createElement('p')
      p.textContent = detail
      bodyEl.appendChild(p)
    }
    if (otherPairs.length) {
      const dl = document.createElement('dl')
      otherPairs.forEach(([k, v]) => {
        const dt = document.createElement('dt'); dt.textContent = k
        const dd = document.createElement('dd'); dd.textContent = v
        dl.appendChild(dt); dl.appendChild(dd)
      })
      bodyEl.appendChild(dl)
    }
    detailsEl.appendChild(summaryEl)
    detailsEl.appendChild(bodyEl)
    container.appendChild(detailsEl)
  }
  return container
}

function enhanceScheduleTables(idx) {
  try {
    const root = msgEls.value[idx]
    if (!root) return
    const table = root.querySelector('.bubble .text table')
    if (!table) return
    if (!isScheduleTable(table)) return
    // 生成・配置
    const acc = buildAccordionFromTable(table)
    let mount = root.querySelector('.bubble .accordion-mount')
    if (!mount) {
      mount = document.createElement('div')
      mount.className = 'accordion-mount'
      const bubble = root.querySelector('.bubble')
      if (bubble) bubble.insertBefore(mount, bubble.firstChild)
    }
    // 既存クリアして追加
    mount.innerHTML = ''
    mount.appendChild(acc)
    // 表示モード既定はアコーディオン
    scheduleStates.value = { ...scheduleStates.value, [idx]: { found: true, mode: 'accordion' } }
    table.classList.add('hidden-table')
  } catch (e) { console.error('enhanceScheduleTables failed', e) }
}

function switchScheduleView(idx, mode) {
  try {
    const root = msgEls.value[idx]
    if (!root) return
    const table = root.querySelector('.bubble .text table')
    const mount = root.querySelector('.bubble .accordion-mount')
    const acc = mount && mount.querySelector('.accordion-block')
    if (!table || !mount || !acc) return
    if (mode === 'table') {
      table.classList.remove('hidden-table')
      mount.style.display = 'none'
    } else {
      table.classList.add('hidden-table')
      mount.style.display = ''
    }
    const st = scheduleStates.value[idx] || { found: true, mode: 'accordion' }
    scheduleStates.value = { ...scheduleStates.value, [idx]: { ...st, mode } }
  } catch {}
}

 </script>

<template>
  <div class="chat" ref="chatEl">
    <div class="log" ref="logEl">
      <div v-for="(m, idx) in messages" :key="idx" :class="['msg', m.role]" :ref="el => setMsgRef(idx, el)">
        <span v-if="m.role !== 'assistant'" class="bubble">{{ m.text }}</span>
        <div v-else class="bubble">
          <div v-if="scheduleStates[idx]?.found" class="schedule-actions">
            <button type="button" class="btn small" :class="{ active: scheduleStates[idx]?.mode==='accordion' }" @click="switchScheduleView(idx, 'accordion')">アコーディオン</button>
            <button type="button" class="btn small" :class="{ active: scheduleStates[idx]?.mode==='table' }" @click="switchScheduleView(idx, 'table')">表</button>
          </div>
          <div class="accordion-mount" v-if="scheduleStates[idx]?.found"></div>
          <div
            v-if="m.text"
            class="text"
            :class="{ 'table-collapsed': (tableStates[idx]?.collapsed && tableStates[idx]?.hasTable) }"
            v-html="renderHtml(m.text)"
          ></div>
          <div v-if="ensureTableState(idx, renderHtml(m.text)).hasTable" class="table-actions">
            <button type="button" class="btn small" @click="toggleTableCollapse(idx)">
              {{ tableStates[idx]?.collapsed ? '表を展開' : '表を折りたたむ' }}
            </button>
            <div class="spacer"></div>
            <button type="button" class="btn small" @click="exportTableAsImage(idx)">画像で保存</button>
            <button type="button" class="btn small" @click="exportTableAsCSV(idx)">CSVで保存</button>
          </div>
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
/* Markdown tables */
.bubble :where(table){
  border-collapse: collapse;
  border-spacing: 0;
  display: block; /* enable horizontal scroll if wide */
  overflow-x: auto;
  width: 100%;
  max-width: 100%;
  margin: 8px 0;
}
.bubble :where(thead){ background: #f8fafc; }
.bubble :where(th, td){
  border: 1px solid #e5e7eb;
  padding: 8px 10px;
  text-align: left;
  vertical-align: top;
  word-break: break-word;
  overflow-wrap: anywhere;
}
.bubble :where(th){ font-weight: 700; color: #111827; }
.bubble :where(tbody tr:nth-child(odd)){ background: #fafafa; }
.bubble :where(caption){ caption-side: bottom; color:#6b7280; font-size: 0.9em; padding-top: 6px; }
.msg.assistant .bubble{ max-width: 100%; } /* 表などを詰め込みすぎないように拡張 */
.hidden-table{ display: none; }
.schedule-actions{ display:flex; gap:8px; margin-bottom: 6px; }
.btn.small.active{ outline: 2px solid #2563eb; }
.accordion-block details{ border:1px solid #e5e7eb; border-radius: 8px; padding: 8px 10px; margin: 6px 0; background:#fff; }
.accordion-block summary{ cursor: pointer; list-style: none; display:flex; align-items:center; gap:10px; }
.accordion-block summary::-webkit-details-marker{ display:none; }
.accordion-block .it-icon{ width: 24px; text-align: center; }
.accordion-block .it-time{ font-weight: 700; color:#111827; min-width:76px; }
.accordion-block .it-title{ font-weight: 600; color:#111827; }
.accordion-block .it-body{ color:#374151; padding: 6px 2px 2px; }
.table-actions{ display:flex; align-items:center; gap:8px; margin-top: 6px; }
.table-actions .spacer{ flex: 1 1 auto; }
.btn.small{ background:#111827; color:#fff; border:none; border-radius:8px; padding:6px 10px; font-size: 12px; }

/* 大きな表の折り畳み */
.text.table-collapsed :where(table){ max-height: 240px; overflow: hidden; position: relative; }
.text.table-collapsed { position: relative; }
.text.table-collapsed::after{
  content: "";
  position: absolute;
  left: 0; right: 0; bottom: 0;
  height: 40px;
  background: linear-gradient(to bottom, rgba(255,255,255,0), rgba(255,255,255,1));
  pointer-events: none;
}
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

/* ダークテーマ（自動） */
@media (prefers-color-scheme: dark) {
  .bubble { background:#111827; color:#e5e7eb; }
  .msg.user .bubble { background:#2563eb; color:#fff; }
  .bubble :where(pre){ background: #0b1220; color:#e5e7eb; }
  .bubble :where(table){ background: #0b1220; }
  .bubble :where(thead){ background: #0f172a; }
  .bubble :where(th, td){ border-color: #334155; }
  .bubble :where(tbody tr:nth-child(odd)){ background: #0f172a; }
  .bubble :where(caption){ color:#94a3b8; }
  .btn.small{ background:#374151; color:#e5e7eb; }
  .text.table-collapsed::after{ background: linear-gradient(to bottom, rgba(17,24,39,0), rgba(17,24,39,1)); }
  .accordion-block details{ border-color:#334155; background:#0b1220; }
  .accordion-block .it-time, .accordion-block .it-title{ color:#e5e7eb; }
  .accordion-block .it-body{ color:#cbd5e1; }
}
</style>
