<script setup>
import { ref, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { getMemory, listPlans, getMemoryVideoStatus } from '@/services/apiClient'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const loading = ref(true)
const error = ref('')
const mem = ref(null)
const plans = ref([])
const videoJobs = ref([])
const allDone = ref(true)
let pollTimer = null

const memoryId = computed(() => {
  const raw = route.params.id
  const s = raw == null ? '' : String(raw).trim()
  if (!s || s.toLowerCase() === 'undefined' || s.toLowerCase() === 'null' || s === 'NaN') return ''
  return s
})

const planTitle = computed(()=>{
  if (!mem.value) return ''
  const p = plans.value.find(x => x.id === mem.value.plan_id)
  return p?.title || mem.value.plan_id || ''
})

function imgSrc(img){
  if (!img) return ''
  const mime = img.image_mime_type || 'image/png'
  return `data:${mime};base64,${img.image_base64}`
}

async function fetchAll(){
  loading.value = true; error.value = ''
  try{
    if (!memoryId.value) { error.value = '無効なURLです'; return }
    const [m, p] = await Promise.all([
      getMemory(memoryId.value, auth.authHeader()),
      listPlans(auth.authHeader())
    ])
    mem.value = m
    plans.value = Array.isArray(p.items)? p.items : []
  videoJobs.value = Array.isArray(m.video_jobs)? m.video_jobs : []
  allDone.value = videoJobs.value.length ? videoJobs.value.every(j=>j.done) : true
  startPollingIfNeeded()
  }catch(e){
    error.value = '読み込みに失敗しました'
  }finally{
    loading.value = false
  }
}

function goBack(){ router.push({ name: 'memories' }) }

onMounted(fetchAll)
watch(() => memoryId.value, () => { fetchAll() })

function startPollingIfNeeded(){
  stopPolling()
  if (!memoryId.value) return
  if (!videoJobs.value.length || videoJobs.value.every(j=>j.done)) return
  pollTimer = setInterval(async ()=>{
    try{
      if (!memoryId.value) { stopPolling(); return }
      const s = await getMemoryVideoStatus(memoryId.value, auth.authHeader())
      videoJobs.value = s.video_jobs || []
      allDone.value = !!s.all_done
      if (allDone.value) stopPolling()
    }catch(e){ /* ignore transient errors */ }
  }, 5000)
}
function stopPolling(){ if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }
function manualRefresh(){ startPollingIfNeeded() }

onBeforeUnmount(() => { stopPolling() })
</script>

<template>
  <div class="memory-detail">
    <header class="header">
      <button class="icon" @click="goBack" aria-label="戻る">←</button>
      <h1>思い出</h1>
    </header>

    <div v-if="loading" class="state">読み込み中...</div>
    <div v-else-if="error" class="state error">{{ error }}</div>
    <div v-else-if="!mem" class="state">見つかりませんでした</div>
    <div v-else class="content">
      <div class="title">関連プラン: {{ planTitle }}</div>
      <div v-if="videoJobs.length" class="video-status">
        <div class="status-line">
          <span class="badge" :class="{done: allDone, pending: !allDone}">{{ allDone ? '動画作成完了' : '動画作成中...' }}</span>
          <button class="secondary small" @click="manualRefresh" :disabled="allDone">更新</button>
        </div>
        <ul class="jobs">
          <li v-for="j in videoJobs" :key="j.index">
            <strong>#{{ j.index+1 }}</strong>
            <span v-if="j.done" class="ok">完了</span>
            <span v-else class="wait">進行中</span>
            <span v-if="j.error" class="err">（{{ j.error }}）</span>
          </li>
        </ul>
      </div>
      <div class="gallery">
        <img v-for="(img,idx) in mem.images" :key="idx" :src="imgSrc(img)" alt="思い出の写真" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.memory-detail { width:100%; height:100%; padding:20px 16px; box-sizing:border-box; overflow:auto; }
.header { display:flex; align-items:center; gap:8px; margin-bottom:12px; }
.icon { background:#f1f5f9; border:none; border-radius:8px; width:32px; height:32px; cursor:pointer; }
.state { color:#475569; }
.state.error { color:#b91c1c; }
.title { font-weight:700; margin: 10px 0 14px; }
.video-status { background:#f8fafc; border:1px solid #e5e7eb; border-radius:10px; padding:10px; margin-bottom:12px; }
.status-line { display:flex; align-items:center; gap:8px; margin-bottom:6px; }
.badge { font-size:12px; padding:4px 8px; border-radius:999px; background:#f59e0b; color:#111827; }
.badge.done { background:#10b981; color:#fff; }
.badge.pending { background:#f59e0b; color:#111; }
.jobs { margin:0; padding-left:18px; color:#374151; }
.jobs .ok { color:#10b981; margin-left:6px; }
.jobs .wait { color:#d97706; margin-left:6px; }
.jobs .err { color:#b91c1c; margin-left:6px; }
.small { padding:6px 8px; font-size:12px; }
.gallery { display:grid; grid-template-columns: repeat(auto-fill, minmax(220px,1fr)); gap:12px; }
.gallery img { width:100%; height:100%; object-fit:cover; border-radius:12px; box-shadow:0 6px 18px #0002; aspect-ratio: 16/9; }
</style>
