<script setup>
import { ref, computed, onMounted } from 'vue'
import { useQuizStore } from '@/stores/quizStore'
import BackButton from '@/components/BackButton.vue'
import { useRouter } from 'vue-router'

const store = useQuizStore()
const router = useRouter()

const minRequired = 3
const selected = ref(new Set())

const options = computed(() => store.likesOptions || [])
const canNext = computed(() => selected.value.size >= minRequired)

function toggle(id) {
  if (selected.value.has(id)) selected.value.delete(id)
  else selected.value.add(id)
}

function next() {
  if (!canNext.value) return
  store.setSelectedLikes(Array.from(selected.value))
  router.push({ name: 'processing' })
  // 処理フロー開始
  setTimeout(() => { try { store.runProcessingFlow() } catch {} }, 0)
}

onMounted(async () => {
  try { await store.fetchLikesOptions() } catch {}
  // 既存選択があれば復元
  if (Array.isArray(store.selectedLikes)) {
    selected.value = new Set(store.selectedLikes)
  }
})
</script>

<template>
  <main class="interests">
    <section class="panel">
      <BackButton :icon-only="true" />
      <h1>好きなことを教えてください</h1>
      <p class="lead">Spotifyのアーティスト選択のように、直感的に選んでください。最低{{ minRequired }}個は選択してください。</p>
      <div class="grid">
        <button
          v-for="opt in options"
          :key="opt.id"
          class="tile"
          :class="{ active: selected.has(opt.id) }"
          type="button"
          @click="toggle(opt.id)"
          :aria-pressed="selected.has(opt.id)"
        >
          <span class="emoji" aria-hidden="true">{{ opt.emoji }}</span>
          <span class="label">{{ opt.label }}</span>
        </button>
      </div>

      <div class="actions">
        <div class="hint">選択数: {{ selected.size }} / {{ minRequired }} 以上</div>
        <button class="primary" :disabled="!canNext" @click="next">次へ</button>
      </div>
    </section>
  </main>
</template>

<style scoped>
.interests { 
  display:grid; 
  place-items:center; 
  min-height:100%; 
  height: 100vh;
  height: 100dvh; /* Use dynamic viewport height for mobile */
  padding:16px; 
  width:100%; 
  overflow-y: auto; /* Ensure vertical scrolling is enabled */
  -webkit-overflow-scrolling: touch; /* Smooth scrolling on iOS */
  box-sizing: border-box;
}
.panel { width:min(920px,100%); background:white; padding:20px; border-radius:16px; box-shadow:0 10px 30px rgba(0,0,0,0.08); }
h1 { margin: 0 0 8px; font-size: 1.6rem; color:#1f2937; }
.lead { color:#5a6b86; margin: 0 0 16px; }
.grid { display:grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.tile { display:flex; flex-direction:column; align-items:center; justify-content:center; gap:8px; padding:14px; border-radius:14px; border:1px solid #e5e7eb; background:#f9fafb; cursor:pointer; transition: transform .06s ease, box-shadow .2s ease, background .2s ease; }
.tile .emoji { font-size: 28px; }
.tile .label { font-weight:600; color: var(--color-text); font-size: 14px; text-align:center; }
.tile:hover { transform: translateY(-1px); box-shadow: 0 6px 16px rgba(45,126,247,0.18); }
.tile.active { background:#e8f0ff; border-color:#cfe0ff; box-shadow: 0 6px 16px rgba(45,126,247,0.25); }
.actions { display:flex; align-items:center; justify-content:space-between; margin-top: 14px; }
.hint { color:#6b7280; font-size: 13px; }
.primary { background:#2d7ef7; color:#fff; border:none; border-radius:10px; padding:10px 16px; font-weight:700; }

@media (max-width: 900px) { .grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 768px) {
  .interests { 
    padding: 0; 
    place-items: stretch;
    /* Ensure proper scrolling on mobile */
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
    overscroll-behavior: contain;
    /* Fix viewport issues */
    height: 100vh;
    height: 100dvh;
  }
  .panel { 
    width: 100%; 
    height: 100vh;
    height: 100dvh;
    border-radius: 0; 
    box-shadow: none; 
    display: flex;
    flex-direction: column;
    justify-content: flex-start; /* Change from center to flex-start to prevent top clipping */
    padding: calc(env(safe-area-inset-top) + 24px) 24px calc(env(safe-area-inset-bottom) + 24px);
    box-sizing: border-box;
    overflow-y: auto; /* Allow scrolling within the panel */
    -webkit-overflow-scrolling: touch;
  }
}
@media (max-width: 600px) {
  .panel { 
    padding: calc(env(safe-area-inset-top) + 16px) 14px calc(env(safe-area-inset-bottom) + 16px); 
    box-sizing: border-box; 
    /* Ensure content is scrollable */
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
  }
  .grid { grid-template-columns: repeat(2, 1fr); gap:8px; }
  .tile { padding:12px; border-radius:12px; }
  .tile .emoji { font-size:24px; }
  .tile .label { font-size: 13px; }
  
  /* Add margin to prevent button from being hidden */
  .actions {
    margin-top: 20px;
    padding-bottom: 20px;
    position: sticky;
    bottom: 0;
    background: white;
    padding-top: 16px;
    border-top: 1px solid #e5e7eb;
  }
}
</style>
