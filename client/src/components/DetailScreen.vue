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
  <p v-if="plan.brief" class="brief">{{ plan.brief }}</p>
      </div>
    </div>
    <div class="wizard-scroll body" aria-labelledby="itinerary-heading">
      <section class="section" aria-labelledby="itinerary-heading">
        <h2 id="itinerary-heading">日程</h2>
        <div v-if="plan.itinerary && plan.itinerary.length" class="itinerary-blocks">
          <div v-for="(day, dIdx) in plan.itinerary" :key="dIdx" class="day-block">
            <h3 class="day-heading">Day {{ day.day || (dIdx+1) }}</h3>
            <ul class="items" v-if="Array.isArray(day.items) && day.items.length">
              <li v-for="(it, iIdx) in day.items" :key="iIdx">
                <span class="time" v-if="it.time">{{ it.time }}</span>
                <span class="title">{{ it.title }}</span>
                <span class="detail" v-if="it.detail"> — {{ it.detail }}</span>
              </li>
            </ul>
            <p v-else class="placeholder small">(項目なし)</p>
          </div>
        </div>
        <p v-else class="placeholder">日程データがありません</p>
      </section>
      <div class="spacer"></div>
    </div>
    <div class="cta-bar">
      <button class="cta secondary" @click="$emit('refine', plan)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M8 2v4"></path>
          <path d="M16 2v4"></path>
          <rect width="18" height="18" x="3" y="4" rx="2"></rect>
          <path d="M3 10h18"></path>
          <path d="M8 14h.01"></path>
          <path d="M12 14h.01"></path>
          <path d="M16 14h.01"></path>
          <path d="M8 18h.01"></path>
          <path d="M12 18h.01"></path>
        </svg>
        ブラッシュアップ
      </button>
      <button class="cta primary" @click="$emit('confirm', plan)">このプランを確定する</button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({
  plan: { type: Object, required: true, default: () => ({ title:'', tags:'', itinerary:[] }) }
})
defineEmits(['go-back', 'confirm', 'refine'])
// ヒーロー画像: タイトルベースで Unsplash プレースホルダ
const heroUrl = computed(() => `url(https://source.unsplash.com/featured/800x600?${encodeURIComponent(props.plan.title||'travel landscape')})`)
</script>

<style scoped>
.detail-screen { position:relative; display:flex; flex-direction:column; padding:0; }
.hero { 
  position:relative; 
  width:100%; 
  aspect-ratio:16/9; 
  min-height:200px;
  max-height:40vh; 
  background:var(--hero-img) center/cover no-repeat; 
  border-bottom-left-radius:24px; 
  border-bottom-right-radius:24px; 
  overflow:hidden; 
  display:flex;
  align-items:flex-end;
}
@media (min-width:640px){ .hero { aspect-ratio:16/7; } }
.hero-overlay { position:absolute; inset:0; background:linear-gradient(to top, rgba(0,0,0,0.55), rgba(0,0,0,0.15)); }
.back-btn { position:absolute; top:10px; left:10px; width:38px; height:38px; border:none; border-radius:12px; background:rgba(255,255,255,0.75); backdrop-filter:blur(6px); display:grid; place-items:center; cursor:pointer; color:#1f2937; box-shadow:0 2px 6px rgba(0,0,0,0.15); }
.back-btn:hover { background:rgba(255,255,255,0.9); }
.back-btn:active { transform:translateY(1px); }
.hero-text { position:absolute; bottom:14px; left:14px; right:14px; color:#fff; text-shadow:0 2px 6px rgba(0,0,0,0.4); }
.hero-text h1 { margin:0 0 4px; font-size:22px; line-height:1.2; font-weight:700; letter-spacing:-.5px; }
.hero-text .tags { margin:0; font-size:12px; opacity:.9; }
.hero-text .brief { margin:4px 0 0; font-size:11px; opacity:.95; max-width:90%; line-height:1.3; }

.body { padding:18px 18px 140px; max-width:640px; width:100%; margin:0 auto; }
.section { background:#fff; border:1px solid #e2e8f0; border-radius:18px; padding:18px 18px 16px; box-shadow:0 4px 14px -4px rgba(0,0,0,0.08); }
.section h2 { margin:0 0 10px; font-size:14px; font-weight:700; letter-spacing:.5px; color:#334155; }
.itinerary { list-style:disc; padding-left:20px; margin:0; display:flex; flex-direction:column; gap:4px; font-size:13px; line-height:1.45; color:#475569; }
.itinerary-blocks { display:flex; flex-direction:column; gap:14px; }
.day-block { background:#f8fafc; border:1px solid #e2e8f0; border-radius:14px; padding:10px 12px 12px; }
.day-heading { margin:0 0 6px; font-size:13px; font-weight:700; color:#334155; letter-spacing:.5px; }
.day-block .items { list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:4px; }
.day-block .items li { font-size:13px; line-height:1.4; color:#475569; display:flex; flex-wrap:wrap; gap:4px; }
.day-block .items .time { font-weight:600; color:#1e293b; min-width:54px; }
.day-block .items .title { font-weight:600; }
.day-block .items .detail { color:#64748b; font-weight:400; }
.placeholder.small { font-size:11px; }
.placeholder { font-size:12px; color:#94a3b8; margin:0; }
.spacer { height:60px; }

.cta-bar { 
  position:fixed; 
  left:0; 
  right:0; 
  bottom:0; 
  padding:12px 14px calc(14px + env(safe-area-inset-bottom)); 
  background:linear-gradient(to top, rgba(255,255,255,0.92), rgba(255,255,255,0.75)); 
  backdrop-filter:blur(10px); 
  display:flex; 
  justify-content:center; 
  gap:8px;
  z-index:50; 
  border-top:1px solid rgba(0,0,0,0.08); 
}

.cta { 
  flex:1;
  max-width:300px; 
  font-weight:600; 
  font-size:15px; 
  padding:14px 20px; 
  border:none; 
  border-radius:999px; 
  cursor:pointer; 
  display:flex;
  align-items:center;
  justify-content:center;
  gap:6px;
  transition:all 0.2s;
}

.cta.primary {
  background:var(--color-primary); 
  color:#fff; 
  box-shadow:0 6px 18px -6px rgba(37,99,235,0.45), 0 0 0 1px #dbeafe inset; 
}

.cta.primary:hover { 
  background:var(--color-primary-hover); 
}

.cta.primary:active { 
  background:var(--color-primary-active); 
  transform:translateY(1px); 
}

.cta.secondary {
  background:#f1f5f9;
  color:#475569;
  border:1px solid #e2e8f0;
  box-shadow:0 2px 8px -2px rgba(0,0,0,0.1);
}

.cta.secondary:hover {
  background:#e2e8f0;
  color:#334155;
  border-color:#cbd5e1;
}

.cta.secondary:active {
  background:#cbd5e1;
  transform:translateY(1px);
}

.cta:focus-visible { 
  outline:2px solid var(--color-focus); 
  outline-offset:2px; 
}

.cta svg {
  width:16px;
  height:16px;
}

@media (min-width:640px){
  .body { padding-left:24px; padding-right:24px; }
  .cta { font-size:16px; }
}
</style>
