<script setup>
import { ref } from 'vue'
import Toast from '@/components/Toast.vue'
import { useAuthStore } from '@/stores/authStore'

// フェーズ: input | loading | suggestion | detail
const phase = ref('input')
const keyword = ref('')
const auth = useAuthStore()
const toast = ref('')

// モック用データ
const suggestions = ref([
  { id: 'relax', title: 'のんびり温泉癒し旅', tags: ['温泉','リラックス','自然'], plan: [
    { day: 1, items: ['10:00 - 温泉街到着、散策','12:00 - 地元の名物で昼食','15:00 - 旅館にチェックイン'] },
    { day: 2, items: ['09:00 - 朝食後、周辺の自然公園へ','13:00 - カフェで休憩','16:00 - 帰路につく'] }
  ]},
  { id: 'history', title: '歴史と文化を巡る旅', tags: ['歴史','寺社仏閣','文化体験'], plan: [
    { day: 1, items: ['10:00 - 古都散策','12:30 - 老舗で昼食','14:00 - 博物館見学'] },
    { day: 2, items: ['09:30 - 神社参拝','11:00 - 伝統工芸体験','15:30 - 夕景撮影'] }
  ]},
  { id: 'active', title: 'アクティブアドベンチャー旅', tags: ['アクティビティ','自然','挑戦'], plan: [
    { day: 1, items: ['08:30 - トレッキング開始','12:00 - 山頂付近で昼食','14:30 - 下山＆温泉'] },
    { day: 2, items: ['09:00 - カヤック体験','13:00 - ローカルランチ','16:00 - 解散'] }
  ]}
])

const selected = ref(null)

function startGenerate(){
  if(!keyword.value.trim()) { toast.value = 'キーワードを入力してください'; return }
  phase.value = 'loading'
  // 実際には API 呼び出し
  setTimeout(()=>{ phase.value='suggestion' }, 1800)
}

function pickPlan(p){ selected.value = p; phase.value='detail' }
function backToSuggestions(){ phase.value='suggestion' }

</script>

<template>
  <main class="min-h-screen text-slate-900" style="background:transparent;">
    <!-- 入力画面 -->
  <section v-if="phase==='input'" id="input-screen" class="relative flex min-h-screen flex-col justify-between p-4">
      <header class="flex items-center justify-center p-4">
        <h1 class="text-lg font-bold tracking-tight">旅行プランの作成</h1>
      </header>
      <div class="flex-grow flex flex-col justify-center items-center gap-8">
        <div class="w-full max-w-md text-center">
          <p class="text-slate-500 text-sm">旅行のキーワードを入力してください</p>
        </div>
        <div class="w-full max-w-md">
          <input v-model="keyword" type="text" placeholder="例: 京都、温泉、2泊3日" class="w-full p-4 bg-white border border-slate-300 rounded-lg text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <button @click="startGenerate" class="w-full max-w-md bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white font-semibold py-3 px-4 rounded-lg transition">プランを作成</button>
      </div>
      <footer></footer>
    </section>

    <!-- ローディング -->
  <section v-else-if="phase==='loading'" id="loading-screen" class="flex flex-col items-center justify-center min-h-screen text-slate-700 p-6" style="background:transparent;">
      <div class="text-lg font-semibold mb-2 tracking-tight">AIが旅行プランを生成中...</div>
      <div class="text-xs text-slate-500 mb-10">最適なプランを考えています。少しお待ちください。</div>
      <div class="relative w-40 h-40 flex items-center justify-center">
        <div class="absolute inset-0 animate-pulse rounded-full bg-blue-100"></div>
        <div class="animate-spin rounded-full h-24 w-24 border-4 border-blue-200 border-t-blue-600"></div>
      </div>
    </section>

    <!-- 提案一覧 -->
  <section v-else-if="phase==='suggestion'" id="suggestion-screen" class="min-h-screen text-slate-900 p-4 pb-20" style="background:transparent;">
      <h1 class="text-center text-xl font-bold my-2 tracking-tight">旅行プランのご提案</h1>
      <p class="text-center text-slate-500 text-sm mb-4">気になるプランを選択してください</p>
      <div class="space-y-3 max-w-xl mx-auto">
        <div v-for="p in suggestions" :key="p.id" class="rounded-xl p-4 bg-white ring-1 ring-slate-200 shadow-sm cursor-pointer active:scale-[0.985] transition hover:shadow-md" @click="pickPlan(p)" tabindex="0" @keydown.enter.prevent="pickPlan(p)">
          <h2 class="font-semibold text-base mb-1 leading-snug">{{ p.title }}</h2>
          <p class="text-xs text-slate-500">{{ p.tags.map(t=>`#${t}`).join(' ') }}</p>
        </div>
      </div>
    </section>

    <!-- 詳細 -->
  <section v-else-if="phase==='detail'" id="detail-screen" class="min-h-screen text-slate-900 p-4 pb-24" style="background:transparent;">
      <div class="max-w-xl mx-auto">
        <button @click="backToSuggestions" class="text-sm text-slate-500 hover:text-slate-700 flex items-center gap-1 mb-2 active:translate-x-[-2px] transition">← 戻る</button>
        <h1 class="text-xl font-bold tracking-tight leading-tight mb-1">{{ selected?.title }}</h1>
        <p class="text-xs text-slate-500 mb-4">{{ selected?.tags.map(t=>`#${t}`).join(' ') }}</p>
        <section aria-labelledby="days-heading" class="bg-white rounded-xl ring-1 ring-slate-200 shadow-sm p-4 space-y-4">
          <h2 id="days-heading" class="font-semibold text-sm mb-2 text-slate-700">日程</h2>
          <div v-for="day in selected?.plan" :key="day.day" class="relative pl-4">
            <p class="font-semibold text-sm mb-1">{{ day.day }}日目</p>
            <ul class="mb-2 space-y-1">
              <li v-for="(it,i) in day.items" :key="i" class="text-xs text-slate-600">{{ it }}</li>
            </ul>
          </div>
        </section>
      </div>
    </section>

    <Toast v-model="toast" :type="toast.includes('失敗') ? 'error' : 'info'" />
  </main>
</template>

<style scoped>
</style>
