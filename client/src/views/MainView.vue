<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { useQuizStore } from '@/stores/quizStore'

const router = useRouter()
const auth = useAuthStore()
const quiz = useQuizStore()
const persona = ref(null)
const loading = ref(true)
const error = ref('')
const hasResult = computed(() => !!quiz.finalResult)

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

function goResults() {
  router.push({ name: 'results' })
}

function restart() {
  router.push({ name: 'home' })
}

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

        <div class="actions">
          <button class="primary" @click="router.push({ name: 'planner' })">旅行計画の作成</button>
        </div>
      </div>
    </section>
  </main>
</template>

<style scoped>
.main { display:grid; place-items:center; padding:32px 16px; }
.panel { width:min(920px,100%); background:white; padding:28px 22px; border-radius:16px; box-shadow:0 10px 30px rgba(0,0,0,0.08); }
.lead { color:#5a6b86; margin: 0 0 16px; }
.muted { color:#6b7280; }
.actions { margin-top: 16px; display:flex; gap: 12px; }
.primary { background:#2d7ef7; color:#fff; border:none; border-radius:10px; padding:10px 16px; }
</style>
