<script setup>
import { ref, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { getMemory, listPlans, getMemoryVideoStatus, planDetail } from '@/services/apiClient'

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
const plan = ref(null)

function fmtDate(s){
  if (!s) return ''
  try {
    const d = new Date(s)
    if (Number.isNaN(d.getTime())) return s
    const y = d.getFullYear()
    const m = String(d.getMonth()+1).padStart(2,'0')
    const dd = String(d.getDate()).padStart(2,'0')
    return `${y}/${m}/${dd}`
  } catch { return s }
}

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

const videoUrls = computed(() => {
  const urls = []
  if (mem.value?.video_urls && Array.isArray(mem.value.video_urls)) {
    for (const u of mem.value.video_urls) if (u) urls.push(u)
  }
  // fallback: collect from jobs
  for (const j of (videoJobs.value||[])) {
    if (j && j.video_public_url && !urls.includes(j.video_public_url)) urls.push(j.video_public_url)
  }
  // ensure primary first if exists
  const primary = mem.value?.primary_video_url
  if (primary) {
    const idx = urls.indexOf(primary)
    if (idx > 0) { urls.splice(idx,1); urls.unshift(primary) }
    else if (idx === -1) { urls.unshift(primary) }
  }
  return urls
})

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
    // fetch plan detail for itinerary rendering
    if (m?.plan_id) {
      try { plan.value = await planDetail(m.plan_id, auth.authHeader()) } catch { plan.value = null }
    }
    videoJobs.value = Array.isArray(m.video_jobs)? m.video_jobs : []
    if (m.primary_video_url) {
      allDone.value = true
    } else {
      allDone.value = videoJobs.value.length ? videoJobs.value.every(j=>j.done) : true
    }
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
      if (s.primary_video_url) {
        mem.value = { ...(mem.value||{}), primary_video_url: s.primary_video_url }
      }
      if (Array.isArray(s.video_urls)) {
        mem.value = { ...(mem.value||{}), video_urls: s.video_urls }
      }
      if (allDone.value) stopPolling()
    }catch(e){ /* ignore transient errors */ }
  }, 5000)
}
function stopPolling(){ if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }
function manualRefresh(){ startPollingIfNeeded() }

onBeforeUnmount(() => { stopPolling() })

const groupedItinerary = computed(()=>{
  const it = (mem.value?.itinerary && mem.value.itinerary.length ? mem.value.itinerary : (plan.value?.itinerary))
  if (!Array.isArray(it) || !it.length) return []
  // Group by it.date (YYYY-MM-DD) or it.day (Day 1, etc). Fallback "スケジュール".
  const groups = []
  const map = new Map()
  for (const item of it){
    const key = item?.date || item?.day || 'スケジュール'
    if (!map.has(key)) map.set(key, [])
    map.get(key).push(item)
  }
  for (const [key, arr] of map.entries()){
    groups.push({ key, items: arr })
  }
  return groups
})
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
  <div v-if="mem?.trip_start_date || mem?.trip_end_date" class="sub">期間: {{ fmtDate(mem?.trip_start_date) }} ~ {{ fmtDate(mem?.trip_end_date) }}</div>
      <div v-if="(!allDone) && (videoJobs.length)" class="video-status">
        <div class="status-line">
          <span class="badge" :class="{done: allDone, pending: !allDone}">{{ allDone ? '動画作成完了' : '動画作成中...' }}</span>
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
      <div v-if="groupedItinerary.length" class="itinerary">
        <h3>日程</h3>
        <div v-if="mem?.summary || mem?.text" class="it-summary">
          <div v-if="mem?.summary" class="sum">{{ mem.summary }}</div>
          <div v-else-if="mem?.text" class="sum">{{ mem.text }}</div>
        </div>
        <div v-for="(g, gi) in groupedItinerary" :key="gi" class="it-group">
          <div class="it-group-header">{{ g.key }}</div>
          <ul class="it-list">
            <li v-for="(it, idx) in g.items" :key="idx" class="it-item">
              <div class="it-node">
                <span class="dot"></span>
                <span class="line" :class="{ last: idx === g.items.length-1 }"></span>
              </div>
              <div class="it-content">
                <div class="it-row">
                  <div class="it-time">{{ it.time || '' }}</div>
                  <div class="it-title">{{ it.title || it.name || it.place || 'スケジュール' }}</div>
                </div>
                <div v-if="it.description || it.note" class="it-desc">{{ it.description || it.note }}</div>
              </div>
            </li>
          </ul>
        </div>
      </div>
      <div class="videos">
        <div v-if="videoUrls.length" class="vgrid">
          <video v-for="(url,i) in videoUrls" :key="i" controls :src="url" class="video-player"></video>
        </div>
        <div v-else class="state">動画を生成中です…</div>
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
.videos { margin-top:12px; }
.vgrid { display:grid; grid-template-columns: repeat(auto-fill, minmax(260px,1fr)); gap:12px; }
.video-player { width:100%; max-height: 60vh; border-radius:12px; box-shadow:0 6px 18px #0002; background:#000; }
/* itinerary */
.itinerary { margin-top: 16px; background:#fff; border:1px solid #e5e7eb; border-radius:12px; padding:10px; }
.itinerary h3 { margin:0 0 8px; font-size:16px; }
.it-group { padding:8px 4px; }
.it-group + .it-group { border-top:1px dashed #e2e8f0; margin-top:8px; padding-top:12px; }
.it-group-header { font-weight:700; color:#0f172a; margin-bottom:8px; }
.it-list { list-style:none; padding:0; margin:0; display:flex; flex-direction:column; gap:12px; }
.it-item { display:grid; grid-template-columns: 20px 1fr; gap:10px; align-items:flex-start; }
.it-node { position:relative; width:20px; display:flex; justify-content:center; }
.it-node .dot { width:10px; height:10px; background:#2563eb; border-radius:50%; position:relative; top:4px; box-shadow:0 0 0 3px rgba(37,99,235,.15); }
.it-node .line { position:absolute; top:14px; bottom:-18px; width:2px; background:#e2e8f0; left:9px; }
.it-node .line.last { display:none; }
.it-content { display:flex; flex-direction:column; gap:4px; padding-bottom:4px; }
.it-row { display:flex; align-items:center; gap:10px; }
.it-time { min-width:64px; font-weight:700; color:#334155; }
.it-title { font-weight:600; }
.it-desc { font-size:13px; color:#475569; }
.it-summary { background:#f8fafc; border:1px dashed #e5e7eb; border-radius:10px; padding:8px; margin:8px 0 10px; }
.it-summary .sum { color:#334155; font-size:14px; white-space:pre-wrap; }
@media (max-width: 480px){
  .memory-detail { padding:16px 12px; }
  .vgrid { grid-template-columns: 1fr; }
  .it-time { min-width:48px; font-size:12px; }
}
</style>
