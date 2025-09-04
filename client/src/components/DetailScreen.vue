<template>
  <div class="wizard-screen detail-screen">
    <div class="hero" :style="{ '--hero-img': heroUrl }">
      <div class="hero-overlay"></div>
      <button class="back-btn" @click="$emit('go-back')" aria-label="戻る">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
      </button>
      <div class="hero-text">
        <h1>{{ plan.title }}</h1>
        <p class="tags">{{ plan.tags }}</p>
      </div>
    </div>
    <div class="wizard-scroll body" aria-labelledby="itinerary-heading">
      <section class="section" aria-labelledby="itinerary-heading">
        <h2 id="itinerary-heading">日程</h2>
        <ul v-if="plan.itinerary && plan.itinerary.length" class="itinerary">
          <li v-for="(item, idx) in plan.itinerary" :key="idx">{{ item }}</li>
        </ul>
        <p v-else class="placeholder">日程データがありません</p>
      </section>
      <div class="spacer"></div>
    </div>
    <div class="cta-bar">
      <button class="cta" @click="$emit('confirm', plan)">このプランを確定する</button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({
  plan: { type: Object, required: true, default: () => ({ title:'', tags:'', itinerary:[] }) }
})
// ヒーロー画像: タイトルベースで Unsplash プレースホルダ
const heroUrl = computed(() => `url(https://source.unsplash.com/featured/800x600?${encodeURIComponent(props.plan.title||'travel landscape')})`)
</script>

<style scoped>
.detail-screen { position:relative; display:flex; flex-direction:column; padding:0; }
.hero { position:relative; width:100%; aspect-ratio:16/10; max-height:46vh; background:var(--hero-img) center/cover no-repeat; border-bottom-left-radius:24px; border-bottom-right-radius:24px; overflow:hidden; }
@media (min-width:640px){ .hero { aspect-ratio:16/7; } }
.hero-overlay { position:absolute; inset:0; background:linear-gradient(to top, rgba(0,0,0,0.55), rgba(0,0,0,0.15)); }
.back-btn { position:absolute; top:10px; left:10px; width:38px; height:38px; border:none; border-radius:12px; background:rgba(255,255,255,0.75); backdrop-filter:blur(6px); display:grid; place-items:center; cursor:pointer; color:#1f2937; box-shadow:0 2px 6px rgba(0,0,0,0.15); }
.back-btn:hover { background:rgba(255,255,255,0.9); }
.back-btn:active { transform:translateY(1px); }
.hero-text { position:absolute; bottom:14px; left:14px; right:14px; color:#fff; text-shadow:0 2px 6px rgba(0,0,0,0.4); }
.hero-text h1 { margin:0 0 4px; font-size:22px; line-height:1.2; font-weight:700; letter-spacing:-.5px; }
.hero-text .tags { margin:0; font-size:12px; opacity:.9; }

.body { padding:18px 18px 140px; max-width:640px; width:100%; margin:0 auto; }
.section { background:#fff; border:1px solid #e2e8f0; border-radius:18px; padding:18px 18px 16px; box-shadow:0 4px 14px -4px rgba(0,0,0,0.08); }
.section h2 { margin:0 0 10px; font-size:14px; font-weight:700; letter-spacing:.5px; color:#334155; }
.itinerary { list-style:disc; padding-left:20px; margin:0; display:flex; flex-direction:column; gap:4px; font-size:13px; line-height:1.45; color:#475569; }
.placeholder { font-size:12px; color:#94a3b8; margin:0; }
.spacer { height:60px; }

.cta-bar { position:fixed; left:0; right:0; bottom:0; padding:12px 14px calc(14px + env(safe-area-inset-bottom)); background:linear-gradient(to top, rgba(255,255,255,0.92), rgba(255,255,255,0.75)); backdrop-filter:blur(10px); display:flex; justify-content:center; z-index:50; border-top:1px solid rgba(0,0,0,0.08); }
.cta { width:100%; max-width:640px; background:var(--color-primary); color:#fff; font-weight:600; font-size:15px; padding:14px 20px; border:none; border-radius:999px; box-shadow:0 6px 18px -6px rgba(37,99,235,0.45), 0 0 0 1px #dbeafe inset; cursor:pointer; }
.cta:hover { background:var(--color-primary-hover); }
.cta:active { background:var(--color-primary-active); transform:translateY(1px); }
.cta:focus-visible { outline:2px solid var(--color-focus); outline-offset:2px; }

@media (min-width:640px){
  .body { padding-left:24px; padding-right:24px; }
  .cta { font-size:16px; }
}
</style>
