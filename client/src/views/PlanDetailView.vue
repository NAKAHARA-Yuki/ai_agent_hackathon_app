<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const plan = ref(null)
const loading = ref(true)
const error = ref('')

async function load(){
  loading.value = true
  error.value = ''
  try {
    const id = route.params.id
    const resp = await fetch(`/api/plans/${id}`, { headers:{ 'Content-Type':'application/json', ...(auth.authHeader()||{}) } })
    if(!resp.ok){ throw new Error('HTTP '+resp.status) }
    plan.value = await resp.json()
  } catch(e){ error.value = '読込に失敗しました'; console.error(e) } finally { loading.value=false }
}

onMounted(load)

function goBack(){ router.back() }
</script>

<template>
  <div class="plan-detail-screen">
    <button class="back" @click="goBack" aria-label="戻る">← 戻る</button>
    <div v-if="loading" class="loading">読み込み中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="plan" class="content">
      <h1 class="title">{{ plan.title }}</h1>
      <p v-if="plan.summary" class="summary">{{ plan.summary }}</p>
      <div v-if="plan.suggestions && plan.suggestions.length" class="suggestions">
        <h2>候補</h2>
        <ul>
          <li v-for="(s,i) in plan.suggestions" :key="i">
            <strong>{{ s.title }}</strong>
            <span v-if="s.tags && s.tags.length" class="tags"> — {{ s.tags.join(' / ') }}</span>
            <span v-if="s.brief" class="brief"> {{ s.brief }}</span>
          </li>
        </ul>
      </div>
      <div v-if="plan.itinerary && plan.itinerary.length" class="itinerary">
        <h2>日程</h2>
        <div v-for="(d,idx) in plan.itinerary" :key="idx" class="day">
          <h3>Day {{ d.day || (idx+1) }}</h3>
          <ul class="items">
            <li v-for="(it,i2) in d.items" :key="i2">
              <span class="time" v-if="it.time">{{ it.time }}</span>
              <span class="item-title">{{ it.title }}</span>
              <span class="item-detail" v-if="it.detail"> — {{ it.detail }}</span>
            </li>
          </ul>
        </div>
      </div>
      <div v-if="plan.text" class="raw-text">
        <h2>本文</h2>
        <pre>{{ plan.text }}</pre>
      </div>
      <div v-if="plan.places && plan.places.length" class="places">
        <h2>場所</h2>
        <ul>
          <li v-for="(p,i) in plan.places" :key="i">{{ p.name }}<small v-if="p.note"> — {{ p.note }}</small></li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.plan-detail-screen{ padding:16px 16px 80px; overflow:auto; height:100%; box-sizing:border-box; display:flex; flex-direction:column; gap:14px; }
.back{ align-self:flex-start; background:#fff; border:1px solid #e2e8f0; padding:6px 12px; border-radius:10px; cursor:pointer; font-size:12px; box-shadow:0 2px 5px rgba(0,0,0,0.05); }
.title{ font-size:20px; font-weight:700; margin:4px 0 0; letter-spacing:-.5px; }
.summary{ margin:4px 0 8px; font-size:13px; color:#475569; line-height:1.5; }
.suggestions ul{ list-style:none; padding:0; margin:4px 0 0; display:flex; flex-direction:column; gap:4px; }
.suggestions li{ font-size:13px; line-height:1.4; }
.suggestions .tags{ color:#64748b; font-size:11px; }
.suggestions .brief{ color:#475569; font-size:11px; }
.itinerary .day{ background:#fff; border:1px solid #e2e8f0; border-radius:14px; padding:10px 12px 12px; margin:8px 0; }
.itinerary h3{ margin:0 0 6px; font-size:13px; font-weight:700; color:#334155; }
.items{ list-style:none; padding:0; margin:0; display:flex; flex-direction:column; gap:4px; }
.items li{ font-size:13px; line-height:1.35; color:#475569; display:flex; flex-wrap:wrap; gap:4px; }
.items .time{ font-weight:600; min-width:56px; }
.raw-text pre{ white-space:pre-wrap; font-size:12px; background:#f8fafc; padding:10px 12px; border-radius:12px; border:1px solid #e2e8f0; }
.places ul{ list-style:disc; padding-left:20px; margin:4px 0 0; display:flex; flex-direction:column; gap:2px; font-size:12px; }
.loading, .error{ font-size:13px; color:#64748b; }
.error{ color:#dc2626; }
</style>
