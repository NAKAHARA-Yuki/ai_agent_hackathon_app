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
      <h1>思い出</h1>
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
            <div class="title">関連プラン: {{ planTitle(mem.plan_id) }}</div>
            <div v-if="mem.trip_start_date || mem.trip_end_date" class="sub">{{ fmtDate(mem.trip_start_date) }} ~ {{ fmtDate(mem.trip_end_date) }}</div>
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
.memories-view { width:100%; height:100%; padding:20px 16px; box-sizing:border-box; overflow:auto; }
.header { display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; }
.state { color:#475569; }
.state.error { color:#b91c1c; }
.primary { background: var(--color-primary, #2563eb); color:#fff; border:none; padding:10px 14px; border-radius:10px; cursor:pointer; }
.secondary { background:#f1f5f9; color:#111827; border:none; padding:10px 14px; border-radius:10px; cursor:pointer; }
.cards { margin-top:8px; }
.empty { color:#64748b; }
.grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap:12px; }
.card { position:relative; aspect-ratio:16/9; border-radius:14px; overflow:hidden; background: var(--hero-img) center/cover no-repeat; box-shadow:0 8px 24px #0001; }
.card .overlay { position:absolute; inset:0; background: linear-gradient(to top, rgba(0,0,0,.5), rgba(0,0,0,.05)); }
.card .text { position:absolute; left:10px; right:10px; bottom:10px; color:#fff; }
.card .title { font-weight:700; text-shadow:0 1px 2px rgba(0,0,0,.4) }
.card .sub { font-size:12px; opacity:.95; margin-top:2px; text-shadow:0 1px 2px rgba(0,0,0,.4) }
.card .count { font-size:12px; opacity:.95 }
.badge { display:inline-block; margin-top:6px; font-size:12px; padding:3px 8px; border-radius:999px; background:#f59e0b; color:#111; }

/* modal */
.modal-backdrop { position:fixed; inset:0; background:#0006; display:grid; place-items:center; z-index:1000; }
.modal { background:#fff; width:min(640px, 92vw); border-radius:12px; box-shadow:0 10px 30px #0003; overflow:hidden; }
.modal-header { display:flex; justify-content:space-between; align-items:center; padding:12px 14px; border-bottom:1px solid #e5e7eb; }
.modal-body { padding:14px; display:flex; flex-direction:column; gap:12px; }
.modal-actions { display:flex; justify-content:flex-end; gap:8px; padding:12px 14px; border-top:1px solid #e5e7eb; }
.icon { background:#f1f5f9; border:none; border-radius:8px; width:32px; height:32px; cursor:pointer; }
.uploads { margin-top:8px; }
.u-grid { display:grid; grid-template-columns: repeat(3, 1fr); gap:8px; }
.u-item { background:#f8fafc; border:1px solid #e5e7eb; border-radius:10px; padding:10px; min-height:64px; display:grid; place-items:center; }
.dates { display:flex; flex-direction:column; gap:6px; }
.date-grid { display:grid; grid-template-columns: repeat(2, 1fr); gap:8px; }
@media (max-width: 480px){
  .memories-view { padding:16px 12px; }
  .grid { grid-template-columns: 1fr; }
  .modal { width: 96vw; }
  .date-grid { grid-template-columns: 1fr; }
}
</style>
