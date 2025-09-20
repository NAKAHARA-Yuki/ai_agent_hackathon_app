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

const planTitle = computed(() => {
  const m = mem.value
  if (!m) return ''
  // Prefer the snapshot title saved on the memory itself
  const mt = (typeof m.title === 'string' ? m.title.trim() : '')
  if (mt) return mt
  // Fallback to the current plan title, then plan_id
  const p = plans.value.find(x => x.id === m.plan_id)
  return p?.title || m.plan_id || ''
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

// itinerary は day/items 構造が保存されている前提でそのまま描画
const itineraryDays = computed(() => Array.isArray(mem.value?.itinerary) ? mem.value.itinerary : [])
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
      

      <!-- Plan info -->
      <div class="plan-info">
        <div class="title">{{ planTitle }}</div>
        <div v-if="mem?.trip_start_date || mem?.trip_end_date" class="sub">期間: {{ fmtDate(mem?.trip_start_date) }} ~ {{ fmtDate(mem?.trip_end_date) }}</div>
      </div>

      <!-- Videos moved to top -->
      <div class="videos">
        <h3 class="section-title">動画</h3>
        <div v-if="videoUrls.length" class="vgrid">
          <video v-for="(url,i) in videoUrls" :key="i" controls :src="url" class="video-player"></video>
        </div>
      </div>

      <!-- Video status -->
      <div v-if="(!allDone) && (videoJobs.length)" class="video-status">
        <div class="status-line">
          <span class="badge" :class="{done: allDone, pending: !allDone}">{{ allDone ? '動画作成完了' : '動画作成中です。この画面のまま３分程度お待ちください...' }}</span>
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

      <!-- Itinerary -->
      <div v-if="itineraryDays.length" class="itinerary">
        <h3 class="section-title">日程</h3>
        <div v-if="mem?.summary || mem?.text" class="it-summary">
          <div v-if="mem?.summary" class="sum">{{ mem.summary }}</div>
          <div v-else-if="mem?.text" class="sum">{{ mem.text }}</div>
        </div>
        <div v-for="(g, gi) in itineraryDays" :key="gi" class="it-group">
          <div class="it-group-header">Day {{ g.day || (gi + 1) }}</div>
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
    </div>
  </div>
</template>

<style scoped>
.memory-detail { 
  width:100%; 
  height:100%; 
  padding:20px 16px; 
  box-sizing:border-box; 
  overflow:auto; 
}

.header { 
  display:flex; 
  align-items:center; 
  gap:12px; 
  margin-bottom:20px; 
  padding-bottom: 12px;
  border-bottom: 1px solid #e5e7eb;
}

.header h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #111827;
}

.icon { 
  background:#f1f5f9; 
  border:none; 
  border-radius:8px; 
  width:36px; 
  height:36px; 
  cursor:pointer; 
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  color: #374151;
  transition: background-color 0.2s ease;
}

.icon:hover {
  background:#e2e8f0;
}

.content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.section-title {
  margin: 0 0 12px 0;
  font-size: 16px;
  font-weight: 600;
  color: #111827;
}

.state { 
  color:#475569; 
  text-align: center;
  padding: 32px 16px;
}

.state.error { 
  color:#b91c1c; 
}

.plan-info {
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 16px;
}

.title { 
  font-weight:600; 
  margin: 0 0 8px 0; 
  color: #111827;
  font-size: 16px;
}

.sub {
  color: #6b7280;
  font-size: 14px;
  margin: 0;
}

.video-status { 
  background:#f8fafc; 
  border:1px solid #e5e7eb; 
  border-radius:12px; 
  padding:16px; 
}

.status-line { 
  display:flex; 
  align-items:center; 
  gap:8px; 
  margin-bottom:8px; 
}

.badge { 
  font-size:12px; 
  padding:6px 12px; 
  border-radius:999px; 
  background:#f59e0b; 
  color:#111827; 
  font-weight: 600;
}

.badge.done { 
  background:#10b981; 
  color:#fff; 
}

.badge.pending { 
  background:#f59e0b; 
  color:#111; 
}

.jobs { 
  margin:0; 
  padding-left:20px; 
  color:#374151; 
}

.jobs .ok { 
  color:#10b981; 
  margin-left:8px; 
  font-weight: 500;
}

.jobs .wait { 
  color:#d97706; 
  margin-left:8px; 
  font-weight: 500;
}

.jobs .err { 
  color:#b91c1c; 
  margin-left:8px; 
}

/* Videos section */
.videos { 
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px;
}

.vgrid { 
  display:grid; 
  grid-template-columns: repeat(auto-fill, minmax(300px,1fr)); 
  gap:16px; 
}

.video-player { 
  width:100%; 
  max-height: 60vh; 
  border-radius:12px; 
  box-shadow:0 6px 18px rgba(0,0,0,0.1); 
  background:#000; 
}

.video-generating {
  text-align: center;
  padding: 32px 16px;
  color: #6b7280;
}

.loading-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.loading-text {
  font-size: 16px;
}

/* Itinerary section */
.itinerary { 
  background:#fff; 
  border:1px solid #e5e7eb; 
  border-radius:12px; 
  padding:20px; 
}

.it-group { 
  padding:12px 0; 
}

.it-group + .it-group { 
  border-top:1px dashed #e2e8f0; 
  margin-top:16px; 
  padding-top:20px; 
}

.it-group-header { 
  font-weight:700; 
  color:#0f172a; 
  margin-bottom:12px; 
  font-size: 15px;
}

.it-list { 
  list-style:none; 
  padding:0; 
  margin:0; 
  display:flex; 
  flex-direction:column; 
  gap:16px; 
}

.it-item { 
  display:grid; 
  grid-template-columns: 24px 1fr; 
  gap:12px; 
  align-items:flex-start; 
}

.it-node { 
  position:relative; 
  width:24px; 
  display:flex; 
  justify-content:center; 
}

.it-node .dot { 
  width:12px; 
  height:12px; 
  background:#2563eb; 
  border-radius:50%; 
  position:relative; 
  top:6px; 
  box-shadow:0 0 0 4px rgba(37,99,235,.15); 
}

.it-node .line { 
  position:absolute; 
  top:18px; 
  bottom:-20px; 
  width:2px; 
  background:#e2e8f0; 
  left:11px; 
}

.it-node .line.last { 
  display:none; 
}

.it-content { 
  display:flex; 
  flex-direction:column; 
  gap:6px; 
  padding-bottom:4px; 
}

.it-row { 
  display:flex; 
  align-items:flex-start; 
  gap:12px; 
  flex-wrap: wrap;
}

.it-time { 
  min-width:72px; 
  font-weight:700; 
  color:#2563eb; 
  font-size: 13px;
  flex-shrink: 0;
}

.it-title { 
  font-weight:600; 
  color: #111827;
  flex: 1;
  min-width: 0;
}

.it-desc { 
  font-size:13px; 
  color:#6b7280; 
  line-height: 1.5;
}

.it-summary { 
  background:#f8fafc; 
  border:1px dashed #e5e7eb; 
  border-radius:10px; 
  padding:12px; 
  margin:0 0 16px 0; 
}

.it-summary .sum { 
  color:#374151; 
  font-size:14px; 
  white-space:pre-wrap; 
  line-height: 1.5;
}

/* Mobile optimizations */
@media (max-width: 768px){
  .memory-detail { 
    padding:16px 12px; 
  }
  
  .vgrid { 
    grid-template-columns: 1fr; 
  }
  
  .videos,
  .itinerary,
  .plan-info {
    padding: 16px;
  }
  
  .content {
    gap: 20px;
  }
}

@media (max-width: 480px){
  .memory-detail { 
    padding:12px 8px; 
  }
  
  .header {
    margin-bottom: 16px;
    gap: 8px;
  }
  
  .header h1 {
    font-size: 16px;
  }
  
  .icon {
    width: 32px;
    height: 32px;
    font-size: 16px;
  }
  
  .it-time { 
    min-width:56px; 
    font-size:12px; 
  }
  
  .it-row {
    flex-direction: column;
    gap: 4px;
    align-items: flex-start;
  }
  
  .it-time {
    min-width: auto;
    margin-bottom: 2px;
  }
  
  .videos,
  .itinerary,
  .plan-info,
  .video-status {
    padding: 12px;
  }
  
  .content {
    gap: 16px;
  }
  
  .section-title {
    font-size: 15px;
  }
  
  .loading-icon {
    font-size: 36px;
  }
  
  .loading-text {
    font-size: 14px;
  }
}
</style>
