<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { getMemory, listPlans } from '@/services/apiClient'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const loading = ref(true)
const error = ref('')
const mem = ref(null)
const plans = ref([])

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
    const [m, p] = await Promise.all([
      getMemory(route.params.id, auth.authHeader()),
      listPlans(auth.authHeader())
    ])
    mem.value = m
    plans.value = Array.isArray(p.items)? p.items : []
  }catch(e){
    error.value = '読み込みに失敗しました'
  }finally{
    loading.value = false
  }
}

function goBack(){ router.push({ name: 'memories' }) }

onMounted(fetchAll)
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
.gallery { display:grid; grid-template-columns: repeat(auto-fill, minmax(220px,1fr)); gap:12px; }
.gallery img { width:100%; height:100%; object-fit:cover; border-radius:12px; box-shadow:0 6px 18px #0002; aspect-ratio: 16/9; }
</style>
