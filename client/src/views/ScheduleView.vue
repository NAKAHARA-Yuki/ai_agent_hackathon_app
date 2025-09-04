<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listPlans } from '@/services/apiClient'
import { useAuthStore } from '@/stores/authStore'

const auth = useAuthStore()
const router = useRouter()
const upcoming = ref([])
const loading = ref(true)
const error = ref('')

async function load(){
  try {
    const j = await listPlans(auth.authHeader())
    upcoming.value = (j.items||[]).map(p=>({
      id: p.id,
      title: p.title,
      summary: p.summary || null,
      brief: p.brief || null,
      date: (p.created_at && p.created_at.seconds ? new Date(p.created_at.seconds*1000) : new Date()).toISOString().slice(0,10),
      status: p.status || 'confirmed'
    }))
  } catch(e){ error.value = '読み込み失敗' } finally { loading.value=false }
}
onMounted(load)
</script>

<template>
  <div class="schedule-screen">
    <h1>旅行予定</h1>
    <p class="subtitle">確定済み / 下書き中の旅程</p>
    <div class="list" role="list" v-if="!loading && upcoming.length">
  <div v-for="p in upcoming" :key="p.id" role="listitem" class="item" :data-status="p.status" @click="router.push({ name:'plan-detail', params:{ id:p.id } })" tabindex="0" @keydown.enter.prevent="router.push({ name:'plan-detail', params:{ id:p.id } })">
        <div class="item-main">
          <div class="date">{{ p.date }}</div>
          <div class="title">{{ p.title }}</div>
          <div v-if="p.summary || p.brief" class="preview">{{ p.summary || p.brief }}</div>
        </div>
        <div class="badge" :class="p.status">{{ p.status === 'confirmed' ? '確定' : '下書き' }}</div>
      </div>
    </div>
    <p v-if="loading" class="empty">読み込み中...</p>
    <p v-else-if="!upcoming.length" class="empty">まだ予定がありません。</p>
    <p v-if="error" class="empty" style="color:#dc2626;">{{ error }}</p>
  </div>
</template>

<style scoped>
.schedule-screen { padding:20px 16px 90px; display:flex; flex-direction:column; gap:12px; width:100%; height:100%; box-sizing:border-box; overflow:auto; }
.schedule-screen h1 { font-size:20px; font-weight:700; margin:4px 0 0; letter-spacing:-.5px; }
.subtitle { margin:0; font-size:12px; color:var(--color-text-subtle); }
.list { display:flex; flex-direction:column; gap:10px; }
.item { position:relative; background:#fff; border:1px solid #e2e8f0; border-radius:16px; padding:14px 14px 12px; display:flex; align-items:center; gap:12px; box-shadow:0 2px 6px rgba(0,0,0,0.05); cursor:pointer; }
.item:active { transform:translateY(1px); }
.item:focus-visible { outline:2px solid var(--color-focus); outline-offset:2px; }
.item-main { flex:1 1 auto; min-width:0; }
.date { font-size:11px; font-weight:600; color:#64748b; letter-spacing:.5px; text-transform:uppercase; }
.title { font-size:14px; font-weight:600; line-height:1.4; color:#1e293b; margin-top:2px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.preview { font-size:11px; line-height:1.3; color:#64748b; margin-top:4px; max-width:100%; display:-webkit-box; -webkit-line-clamp:2; line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
.badge { font-size:11px; line-height:1; padding:6px 10px 5px; border-radius:999px; font-weight:600; letter-spacing:.5px; background:#f1f5f9; color:#475569; }
.badge.confirmed { background:#dbeafe; color:#1d4ed8; }
.badge.draft { background:#fef3c7; color:#b45309; }
.empty { font-size:12px; color:var(--color-text-subtle); margin-top:24px; text-align:center; }
</style>
