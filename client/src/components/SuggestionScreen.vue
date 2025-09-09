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

// 画像の処理: 生成された画像があればそれを使用、なければUnsplashのランダム画像をフォールバック
const keywords = ['travel','landscape','japan','city','nature','culture','ocean','mountain']
const enrichedPlans = computed(() => props.plans.map((p, idx) => {
  let image
  
  // Check if the plan has a generated image
  if (p.image_url) {
    // Use the generated image from the server
    image = p.image_url.startsWith('http') ? p.image_url : `http://localhost:8080${p.image_url}`
  } else {
    // Fallback to Unsplash (original behavior)
    const key = encodeURIComponent(((p.title||'') + ' ' + keywords[idx % keywords.length]).trim())
    image = `https://source.unsplash.com/featured/400x300?${key}`
  }
  
  return { raw: p, id: p.id, image }
}))
</script>

<style scoped>
.suggestions-screen { padding:16px 16px 24px; display:flex; flex-direction:column; gap:16px; }
.header h1 { margin:4px 0 0; font-size:20px; font-weight:700; letter-spacing:-.5px; text-align:center; }
.header .tagline { margin:4px 0 4px; text-align:center; font-size:12px; color:var(--color-text-subtle); }
/* 縦一列表示 */
.cards { display:flex; flex-direction:column; gap:18px; padding:4px 2px 40px; }
.card { position:relative; width:100%; height:180px; border-radius:18px; overflow:hidden; cursor:pointer; isolation:isolate; background:#ddd; display:flex; }
.card::before { content:""; position:absolute; inset:0; background:var(--bg-img) center/cover no-repeat; filter:brightness(1) saturate(1.1); transition:transform .6s ease; }
.card-overlay { position:absolute; inset:0; background:linear-gradient(to top, rgba(0,0,0,0.55), rgba(0,0,0,0.05)); mix-blend-mode:multiply; }
.card-content { position:relative; z-index:2; margin-top:auto; padding:14px 16px 14px; color:#fff; text-shadow:0 2px 4px rgba(0,0,0,.4); display:flex; flex-direction:column; gap:6px; }
.title { font-size:16px; font-weight:600; line-height:1.3; margin:0; letter-spacing:.2px; }
.tags { margin:0; font-size:12px; opacity:.9; overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:1; -webkit-box-orient:vertical; }
.card:focus-visible { outline:2px solid var(--color-focus); outline-offset:2px; }
.card:hover::before { transform:scale(1.05); }
.card:active { transform:scale(.97); }
@media (min-width:640px){
  .card { height:200px; }
  .title { font-size:18px; }
}
</style>
