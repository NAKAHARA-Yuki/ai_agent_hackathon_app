<script setup>
import { ref } from 'vue'
import { useAuthStore } from '@/stores/authStore'

const auth = useAuthStore()

const messages = ref([
  { role: 'assistant', text: 'こんにちは。どんな旅がしたいですか？（例: 美術館めぐり、温泉、自然、グルメ）' }
])
const userInput = ref('')

// 親へ: エージェント応答に含まれる場所候補を通知
const emit = defineEmits(['agent-update'])

async function sendMessage() {
  const text = userInput.value.trim()
  if (!text) return
  messages.value.push({ role: 'user', text })
  userInput.value = ''

  // サーバーのエージェントに問い合わせ（簡易プロトタイプ）
  try {
    const resp = await fetch('/api/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...auth.authHeader() },
      body: JSON.stringify({ message: text })
    })
    if (!resp.ok) throw new Error('failed')
    const data = await resp.json()
    const reply = data.reply || '提案を取得できませんでした。'
    messages.value.push({ role: 'assistant', text: reply })

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
      emit('agent-update', { reply, places })
    } else {
      emit('agent-update', { reply })
    }
  } catch (e) {
    messages.value.push({ role: 'assistant', text: 'エラーが発生しました。少し待って再試行してください。' })
  }
}
</script>

<template>
  <div class="chat">
    <div class="log">
      <div v-for="(m, idx) in messages" :key="idx" :class="['msg', m.role]">
        <span class="bubble">{{ m.text }}</span>
      </div>
    </div>
    <form class="composer" @submit.prevent="sendMessage">
      <input v-model="userInput" type="text" placeholder="行きたい雰囲気や目的を自由に入力..." />
      <button type="submit">送信</button>
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
.composer { display:flex; gap:8px; border-top:1px solid #eee; padding:12px; align-items:center; }
/* 入力欄: 広め、送信ボタン: 固定幅で比率を安定化（約85:15想定） */
.composer input { flex: 1 1 auto; min-width: 0; padding:10px 12px; border-radius:8px; border:1px solid #e5e7eb; font-size:14px; }
.composer button { flex: 0 0 112px; height: 40px; background:#2d7ef7; color:#fff; border:none; border-radius:8px; font-weight:600; }

@media (max-width: 600px) {
  /* モバイルではボタン幅を少し小さくする（約80:20） */
  .composer button { flex-basis: 96px; }
}
</style>
