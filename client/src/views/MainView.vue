<script setup>
import { onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/authStore'

const auth = useAuthStore()
const persona = ref(null)
const loading = ref(true)
const error = ref('')

async function loadLatestPersona() {
  try {
    const resp = await fetch('/api/persona/latest', { headers: { ...auth.authHeader() } })
    if (resp.ok) {
      persona.value = await resp.json()
    } else {
      persona.value = null
    }
  } catch (e) {
    error.value = e?.message || '読み込みに失敗しました'
  } finally {
    loading.value = false
  }
}

onMounted(loadLatestPersona)
</script>

<template>
  <main class="main">
    <section class="panel">
      <h1>メインページ</h1>
      <p class="lead">あなたの診断に基づき、パーソナライズされた旅の提案を続けられます。</p>

      <div v-if="loading">読み込み中...</div>
      <div v-else>
        <div v-if="persona && persona.profile">
          <h3>現在のタイプ: {{ persona.profile.title }}</h3>
          <p>{{ persona.profile.description }}</p>
        </div>
        <div v-else class="muted">まだペルソナがありません。診断を実施してください。</div>
      </div>
    </section>
  </main>
</template>

<style scoped>
.main { display:grid; place-items:center; padding:32px 16px; }
.panel { width:min(920px,100%); background:white; padding:28px 22px; border-radius:16px; box-shadow:0 10px 30px rgba(0,0,0,0.08); }
.lead { color:#5a6b86; margin: 0 0 16px; }
.muted { color:#6b7280; }
</style>
