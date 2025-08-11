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
      emit('agent-update', { reply, places: data.places })
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
.composer { display:flex; gap:8px; border-top:1px solid #eee; padding:8px; }
.composer input { flex:1; padding:10px 12px; border-radius:8px; border:1px solid #e5e7eb; }
.composer button { padding:10px 14px; background:#2d7ef7; color:#fff; border:none; border-radius:8px; }
</style>
