<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { listPlans, listMemories, createMemory } from '@/services/apiClient'

const auth = useAuthStore()
const router = useRouter()

const loading = ref(true)
const error = ref('')
const items = ref([])
const showModal = ref(false)
const saving = ref(false)

// form state
const selectedPlanId = ref('')
const images = ref([null, null, null]) // { image_base64, image_mime_type }
const plansOptions = ref([])
// trip dates
const tripStart = ref('')
const tripEnd = ref('')

function toDate(val){
  try {
    if (!val) return null
    if (val instanceof Date) return val
    if (typeof val === 'number') return new Date(val)
    if (typeof val === 'string') return new Date(val)
    if (typeof val === 'object'){
      // Firestore Timestamp like { seconds, nanos } or {_seconds}
      const sec = val.seconds ?? val._seconds
      if (typeof sec === 'number') return new Date(sec * 1000)
    }
    return null
  } catch { return null }
}
function fmtDate(s){
  const d = toDate(s)
  if (!d || Number.isNaN(d.getTime())) return typeof s === 'string' ? s : ''
  const y = d.getFullYear()
  const m = String(d.getMonth()+1).padStart(2,'0')
  const dd = String(d.getDate()).padStart(2,'0')
  return `${y}/${m}/${dd}`
}

function memoryDateRange(mem){
  if (!mem) return ''
  const ds = toDate(mem.trip_start_date)
  const de = toDate(mem.trip_end_date)
  if (ds || de){
    if (ds && de) return `${fmtDate(ds)} ~ ${fmtDate(de)}`
    if (ds) return `${fmtDate(ds)}`
    if (de) return `${fmtDate(de)}`
  }
  // fallback to itinerary dates
  const it = Array.isArray(mem.itinerary) ? mem.itinerary : []
  const dates = it.map(x=>toDate(x?.date)).filter(d=>d && !Number.isNaN(d.getTime()))
  if (dates.length){
    dates.sort((a,b)=>a-b)
    const first = dates[0], last = dates[dates.length-1]
    if (first && last && first.getTime() !== last.getTime()) return `${fmtDate(first)} ~ ${fmtDate(last)}`
    return fmtDate(first)
  }
  // fallback to created_at
  const created = toDate(mem.created_at)
  if (created) return fmtDate(created)
  return ''
}

async function fetchAll(){
  loading.value = true; error.value = ''
  try {
    const [mem, plans] = await Promise.all([
      listMemories(auth.authHeader()),
      listPlans(auth.authHeader())
    ])
    items.value = Array.isArray(mem.items)? mem.items : []
    plansOptions.value = Array.isArray(plans.items)? plans.items : []
  } catch(e){
    error.value = '読み込みに失敗しました'
  } finally {
    loading.value = false
  }
}

function openModal(){
  selectedPlanId.value = plansOptions.value[0]?.id || ''
  images.value = [null,null,null]
  tripStart.value = ''
  tripEnd.value = ''
  showModal.value = true
}
function closeModal(){
  showModal.value = false
}

async function onFileChange(idx, evt){
  const file = evt.target.files?.[0]
  if(!file) { images.value[idx] = null; return }
  const b64 = await toBase64(file)
  images.value[idx] = { image_base64: b64, image_mime_type: file.type || 'image/png' }
}

function toBase64(file){
  return new Promise((resolve,reject)=>{
    const reader = new FileReader()
    reader.onload = ()=>{
      const result = reader.result
      // result is dataURL; extract base64 part
      const s = String(result||'')
      const idx = s.indexOf(',')
      resolve(idx>=0? s.slice(idx+1) : s)
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

const canSave = computed(()=> selectedPlanId.value && images.value.some(Boolean))

// Helper: resolve plan title from id
function planTitle(id){
  const p = plansOptions.value.find(x => x.id === id)
  return p?.title || id || ''
}

async function save(){
  if(!canSave.value || saving.value) return
  saving.value = true
  try{
    const imgs = images.value.filter(Boolean).slice(0,3)
  const payload = { plan_id: selectedPlanId.value, images: imgs }
  if (tripStart.value) payload.trip_start_date = tripStart.value
  if (tripEnd.value) payload.trip_end_date = tripEnd.value
  await createMemory(payload, auth.authHeader())
    await fetchAll()
    showModal.value = false
  }catch(e){
    alert('登録に失敗しました。時間をおいて再試行してください。')
  }finally{
    saving.value = false
  }
}

function heroStyle(mem){
  const first = (mem.images||[])[0]
  if(first && first.image_base64){
    const mime = first.image_mime_type || 'image/png'
    return { '--hero-img': `url(data:${mime};base64,${first.image_base64})` }
  }
  return { '--hero-img': 'url(https://source.unsplash.com/featured/800x600?travel%20memories)'}
}

function openDetail(mem){
  if (!mem?.id) return
  router.push({ name: 'memory-detail', params: { id: mem.id } })
}

onMounted(fetchAll)
</script>

<template>
  <div class="memories-view">
    <header class="header">
      <h1>旅の思い出たち</h1>
      <button class="primary" @click="openModal" aria-label="思い出を追加">思い出を追加</button>
    </header>

    <div v-if="loading" class="state">読み込み中...</div>
    <div v-else-if="error" class="state error">{{ error }}</div>
    <div v-else class="cards">
      <div v-if="!items.length" class="empty">まだ思い出がありません。右上の「思い出を追加」から登録できます。</div>
      <div v-else class="grid">
        <div v-for="mem in items" :key="mem.id" class="card" :style="heroStyle(mem)" @click="openDetail(mem)">
          <div class="overlay"></div>
          <div class="text">
            <div class="title">{{ planTitle(mem.plan_id) }}の思い出</div>
            <div v-if="memoryDateRange(mem)" class="sub">{{ memoryDateRange(mem) }}</div>
            <div class="count">写真 {{ (mem.images||[]).length }} 枚</div>
            <div v-if="(mem.video_jobs||[]).some(j=>!j.done)" class="badge">動画作成中</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal -->
    <div v-if="showModal" class="modal-backdrop" @click="closeModal">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <h2>思い出を追加</h2>
          <button class="icon" @click="closeModal" aria-label="閉じる">×</button>
        </div>
        <div class="modal-body">
          <label>旅行予定を選択</label>
          <select v-model="selectedPlanId">
            <option v-for="p in plansOptions" :key="p.id" :value="p.id">{{ p.title || p.id }}</option>
          </select>

          <div class="dates">
            <label>旅行日程</label>
            <div class="date-grid">
              <div>
                <small>開始日</small>
                <input type="date" v-model="tripStart" />
              </div>
              <div>
                <small>終了日</small>
                <input type="date" v-model="tripEnd" />
              </div>
            </div>
          </div>

          <div class="uploads">
            <label>写真をアップロード（最大3枚）</label>
            <div class="u-grid">
              <div class="u-item" v-for="i in 3" :key="i">
                <input type="file" accept="image/*" @change="(e)=>onFileChange(i-1,e)" />
              </div>
            </div>
          </div>
        </div>
        <div class="modal-actions">
          <button class="secondary" @click="closeModal">キャンセル</button>
          <button class="primary" :disabled="!canSave || saving" @click="save">{{ saving? '登録中...' : '登録' }}</button>
        </div>
      </div>
    </div>
  </div>
  
</template>

<style scoped>
.memories-view { 
  width:100%; 
  height:100%; 
  padding:20px 16px; 
  box-sizing:border-box; 
  overflow:auto; 
}

.header { 
  display:flex; 
  justify-content:flex-start; 
  align-items:center; 
  margin-bottom:16px; 
  gap:12px; 
  flex-wrap: wrap; /* allow wrapping on narrow screens to avoid overlap */
}

.header h1 { 
  margin:0; 
  font-size:20px; 
  line-height:1.2; 
  flex: 1 1 auto; /* take available space but allow shrink */
  min-width: 0; /* Allow text to shrink */
  white-space: nowrap; /* Keep on one line */
  overflow: hidden; /* Clip overflow */
  text-overflow: ellipsis; /* Show ellipsis when clipped */
  writing-mode: horizontal-tb; /* Force horizontal layout */
}

.header .primary { 
  font-size:14px; 
  padding:8px 12px; 
  height:36px; 
  display:inline-flex; 
  align-items:center; 
  border-radius:10px; 
  white-space:nowrap;
  flex-shrink: 0; /* Prevent button from shrinking */
  margin-left: auto; /* push button to the far right */
}

.state { color:#475569; }
.state.error { color:#b91c1c; }

.primary { 
  background: var(--color-primary, #2563eb); 
  color:#fff; 
  border:none; 
  padding:10px 14px; 
  border-radius:10px; 
  cursor:pointer; 
  transition: background-color 0.2s ease;
}

.primary:hover {
  background: var(--color-primary-dark, #1d4ed8);
}

.secondary { 
  background:#f1f5f9; 
  color:#111827; 
  border:none; 
  padding:10px 14px; 
  border-radius:10px; 
  cursor:pointer; 
  transition: background-color 0.2s ease;
}

.secondary:hover {
  background:#e2e8f0;
}

.cards { margin-top:8px; }
.empty { 
  color:#64748b; 
  text-align: center;
  padding: 32px 16px;
  line-height: 1.6;
}

.grid { 
  display:grid; 
  grid-template-columns: repeat(auto-fit, minmax(280px, 320px)); 
  gap:16px; 
  width: 100%;
  justify-content: center; /* center columns horizontally */
  margin: 0 auto; /* center the grid container */
  max-width: 1200px; /* keep readable width on desktop */
}

.card { 
  position:relative; 
  aspect-ratio:16/9; 
  border-radius:14px; 
  overflow:hidden; 
  background: var(--hero-img) center/cover no-repeat; 
  box-shadow:0 8px 24px rgba(0,0,0,0.08); 
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.card:hover {
  transform: translateY(-2px);
  box-shadow:0 12px 32px rgba(0,0,0,0.12);
}

.card .overlay { 
  position:absolute; 
  inset:0; 
  background: linear-gradient(to top, rgba(0,0,0,.6), rgba(0,0,0,.1)); 
}

.card .text { 
  position:absolute; 
  left:12px; 
  right:12px; 
  bottom:12px; 
  color:#fff; 
}

.card .title { 
  font-weight:700; 
  text-shadow:0 1px 2px rgba(0,0,0,.6);
  margin-bottom: 4px;
}

.card .sub { 
  font-size:12px; 
  opacity:.95; 
  margin-top:2px; 
  text-shadow:0 1px 2px rgba(0,0,0,.6);
}

.card .count { 
  font-size:12px; 
  opacity:.95;
  margin-top: 2px;
}

.badge { 
  display:inline-block; 
  margin-top:6px; 
  font-size:11px; 
  padding:4px 8px; 
  border-radius:999px; 
  background:#f59e0b; 
  color:#111; 
  font-weight: 600;
}

/* modal */
.modal-backdrop { 
  position:fixed; 
  inset:0; 
  background:rgba(0,0,0,0.5); 
  display:grid; 
  place-items:center; 
  z-index:1000; 
  padding: 16px;
  box-sizing: border-box;
}

.modal { 
  background:#fff; 
  width:min(640px, 100%); 
  max-height: 90vh;
  border-radius:12px; 
  box-shadow:0 10px 30px rgba(0,0,0,0.2); 
  overflow:hidden; 
  display: flex;
  flex-direction: column;
}

.modal-header { 
  display:flex; 
  justify-content:space-between; 
  align-items:center; 
  padding:16px 20px; 
  border-bottom:1px solid #e5e7eb; 
  flex-shrink: 0;
}

.modal-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.modal-body { 
  padding:20px; 
  display:flex; 
  flex-direction:column; 
  gap:16px; 
  overflow-y: auto;
  flex: 1;
}

.modal-body label {
  font-weight: 600;
  color: #374151;
  margin-bottom: 4px;
  display: block;
}

.modal-body select,
.modal-body input[type="date"] {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 14px;
  box-sizing: border-box;
}

.modal-actions { 
  display:flex; 
  justify-content:flex-end; 
  gap:12px; 
  padding:16px 20px; 
  border-top:1px solid #e5e7eb; 
  flex-shrink: 0;
}

.icon { 
  background:#f1f5f9; 
  border:none; 
  border-radius:8px; 
  width:32px; 
  height:32px; 
  cursor:pointer; 
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  transition: background-color 0.2s ease;
}

.icon:hover {
  background:#e2e8f0;
}

.uploads { margin-top:8px; }

.u-grid { 
  display:grid; 
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); 
  gap:12px; 
}

.u-item { 
  background:#f8fafc; 
  border:1px solid #e5e7eb; 
  border-radius:10px; 
  padding:12px; 
  min-height:80px; 
  display:grid; 
  place-items:center; 
  transition: border-color 0.2s ease;
}

.u-item:hover {
  border-color: #d1d5db;
}

.u-item input[type="file"] {
  font-size: 12px;
  width: 100%;
}

.dates { 
  display:flex; 
  flex-direction:column; 
  gap:8px; 
}

.date-grid { 
  display:grid; 
  grid-template-columns: repeat(2, 1fr); 
  gap:12px; 
}

.date-grid > div {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.date-grid small {
  font-size: 12px;
  color: #6b7280;
  font-weight: 500;
}

/* Mobile optimizations */
@media (max-width: 640px){
  .memories-view { 
    padding:16px 12px; 
  }
  
  .header { 
    align-items: center;
    gap: 8px;
  }
  
  .header h1 { 
    font-size:18px; 
  }
  
  .header .primary { 
    height:36px; 
    font-size:12px; 
    padding:8px 12px; 
  }
  
  .grid { 
    grid-template-columns: 1fr; 
    gap: 12px;
  }
  
  .modal { 
    width: calc(100vw - 32px);
    margin: 16px;
  }
  
  .modal-header,
  .modal-body,
  .modal-actions {
    padding-left: 16px;
    padding-right: 16px;
  }
  
  .date-grid { 
    grid-template-columns: 1fr; 
    gap: 8px;
  }
  
  .u-grid {
    grid-template-columns: 1fr;
    gap: 8px;
  }
  
  .empty {
    padding: 24px 12px;
    font-size: 14px;
  }
}

@media (max-width: 480px){
  .memories-view { 
    padding:12px 8px; 
  }
  
  .header .primary { 
    height:34px; 
    font-size:11px; 
    padding:6px 10px; 
  }
  
  .modal {
    width: calc(100vw - 24px);
    margin: 12px;
  }
  
  .modal-header,
  .modal-body,
  .modal-actions {
    padding-left: 12px;
    padding-right: 12px;
  }
}
</style>
