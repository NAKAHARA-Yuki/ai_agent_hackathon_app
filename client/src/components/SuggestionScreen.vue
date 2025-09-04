<template>
  <div class="wizard-screen suggestions-screen">
    <div class="header">
      <h1>旅行プランのご提案</h1>
      <p class="tagline">気になるプランを選択してください</p>
    </div>
    <div class="wizard-scroll cards" role="list">
      <div
        v-for="plan in enrichedPlans"
        :key="plan.id"
        role="listitem"
        class="card"
        :style="{ '--bg-img': `url(${plan.image})` }"
        tabindex="0"
        @click="$emit('select-plan', plan.raw)"
        @keydown.enter.prevent="$emit('select-plan', plan.raw)"
      >
        <div class="card-overlay"></div>
        <div class="card-content">
          <h2 class="title">{{ plan.raw.title }}</h2>
          <p class="tags">{{ plan.raw.tags }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ plans: { type: Array, default: () => [] } })
defineEmits(['select-plan'])

// 簡易画像割当: タイトル + id を seed に Unsplash のランダムサムネイル（将来は API/自前画像に差し替え可）
const keywords = ['travel','landscape','japan','city','nature','culture','ocean','mountain']
const enrichedPlans = computed(() => props.plans.map((p, idx) => {
  const key = encodeURIComponent(((p.title||'') + ' ' + keywords[idx % keywords.length]).trim())
  return { raw: p, id: p.id, image: `https://source.unsplash.com/featured/400x300?${key}` }
}))
</script>

<style scoped>
.suggestions-screen { padding:16px 16px 24px; display:flex; flex-direction:column; gap:12px; }
.header h1 { margin:4px 0 0; font-size:20px; font-weight:700; letter-spacing:-.5px; text-align:center; }
.header .tagline { margin:4px 0 4px; text-align:center; font-size:12px; color:var(--color-text-subtle); }
.cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr)); gap:14px; padding:4px 2px 92px; }
.card { position:relative; aspect-ratio:4/3; border-radius:18px; overflow:hidden; cursor:pointer; isolation:isolate; background:#ddd; display:flex; }
.card::before { content:""; position:absolute; inset:0; background:var(--bg-img) center/cover no-repeat; filter:brightness(1) saturate(1.1); transition:transform .6s ease; }
.card-overlay { position:absolute; inset:0; background:linear-gradient(to top, rgba(0,0,0,0.55), rgba(0,0,0,0.05)); mix-blend-mode:multiply; }
.card-content { position:relative; z-index:2; margin-top:auto; padding:10px 12px 10px; color:#fff; text-shadow:0 2px 4px rgba(0,0,0,.4); display:flex; flex-direction:column; gap:2px; }
.title { font-size:14px; font-weight:600; line-height:1.25; margin:0; letter-spacing:.2px; }
.tags { margin:0; font-size:10px; opacity:.85; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.card:focus-visible { outline:2px solid var(--color-focus); outline-offset:2px; }
.card:hover::before { transform:scale(1.06); }
.card:active { transform:scale(.97); }
@media (min-width:640px){
  .cards { grid-template-columns:repeat(auto-fill,minmax(190px,1fr)); }
  .title { font-size:15px; }
}
</style>
