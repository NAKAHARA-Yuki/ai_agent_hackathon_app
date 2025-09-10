<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { listPlans } from '@/services/apiClient'
import BackButton from '@/components/BackButton.vue'
import Toast from '@/components/Toast.vue'

const auth = useAuthStore()
const router = useRouter()
const loading = ref(false)
const items = ref([])
const error = ref('')
const toast = ref('')

async function fetchPlans() {
  loading.value = true
  error.value = ''
  try {
  const j = await listPlans(auth.authHeader())
    items.value = Array.isArray(j.items) ? j.items.sort((a,b) => (b.created_at||'') > (a.created_at||'') ? 1 : -1) : []
  } catch (e) {
    error.value = '読み込みに失敗しました'
  } finally { loading.value = false }
}

function openDetail(it){
  // Navigate to plan detail view
  router.push({ name: 'plan-detail', params: { id: it.id } })
}

onMounted(fetchPlans)
</script>

<template>
  <main class="plans-list">
    <header class="header">
      <BackButton :icon-only="true" icon="chevron-left" label="戻る" :fallback-name="'main'" />
      <h1>保存したプラン</h1>
    </header>
    <div v-if="loading" class="state">読み込み中...</div>
    <div v-else-if="error" class="state error">{{ error }}</div>
    <div v-else class="cards" v-auto-animate>
      <div v-for="p in items" :key="p.id" class="card" @click="openDetail(p)" role="button" :aria-label="p.title">
        <div class="title">{{ p.title || '無題プラン' }}</div>
        <div class="meta">{{ p.created_at || '' }}</div>
      </div>
      <p v-if="!items.length" class="empty">まだ保存されたプランはありません。</p>
    </div>
    <Toast v-model="toast" />
  </main>
</template>

<style scoped>
.plans-list { display:flex; flex-direction:column; gap:12px; width:100%; }
.header { display:flex; align-items:center; gap:12px; background:rgba(255,255,255,0.9); padding:8px 10px; border-radius:12px; box-shadow:0 4px 10px rgba(0,0,0,0.05); }
.header h1 { font-size:18px; margin:0; flex:1; }
.state { padding:20px; text-align:center; color:#374151; }
.state.error { color:#b91c1c; }
.cards { display:grid; grid-template-columns: repeat(auto-fill, minmax(220px,1fr)); gap:12px; }
.card { background: var(--color-surface); border:1px solid var(--color-border); border-radius:14px; padding:14px 16px; box-shadow:0 6px 14px rgba(0,0,0,0.05); display:flex; flex-direction:column; gap:6px; cursor:pointer; }
.card:active { transform: translateY(1px); }
.card .title { font-weight:600; font-size:14px; color: var(--color-text); line-height:1.3; }
.card .meta { font-size:11px; color:#6b7280; }
.empty { text-align:center; padding:30px 10px; color:#6b7280; grid-column:1/-1; }
@media (max-width: 600px){ .cards { grid-template-columns: repeat(auto-fill, minmax(150px,1fr)); } }
</style>
