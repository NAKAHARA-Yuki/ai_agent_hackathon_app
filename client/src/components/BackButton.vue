<script setup>
import { useRouter } from 'vue-router'

const props = defineProps({
  label: { type: String, default: '戻る' },
  fallbackName: { type: String, default: 'home' },
  fallbackTo: { type: [Object, String], default: null },
  iconOnly: { type: Boolean, default: false },
  icon: { type: String, default: 'arrow' } // 'arrow' | 'home'
})

const router = useRouter()

function goBack() {
  try {
    if (window.history.length > 1) {
      router.back()
      return
    }
  } catch {}
  const dest = props.fallbackTo || (props.fallbackName ? { name: props.fallbackName } : { path: '/' })
  router.push(dest)
}
</script>

<template>
  <button
    class="back-btn"
    :class="{ icon: iconOnly }"
    type="button"
    @click="goBack"
    :aria-label="iconOnly ? (label || '戻る') : '戻る'"
    :title="iconOnly ? (label || '戻る') : ''"
  >
    <template v-if="iconOnly">
      <svg v-if="icon === 'home'" aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 12l9-9 9 9"></path>
        <path d="M9 21V9h6v12"></path>
      </svg>
      <svg v-else aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M15 18l-6-6 6-6"></path>
      </svg>
    </template>
    <template v-else>
      ← {{ label }}
    </template>
  </button>
  
</template>

<style scoped>
.back-btn {
  appearance: none;
  background: transparent;
  border: 1px solid #e5e7eb;
  color: #111827;
  border-radius: 10px;
  padding: 6px 10px;
  font-weight: 600;
  cursor: pointer;
}
.back-btn:hover { background: #f3f4f6; }

.back-btn.icon {
  width: 40px;
  height: 40px;
  display: inline-grid;
  place-items: center;
  border-radius: 50%;
  padding: 0;
  transition: background 0.2s ease;
}
.back-btn.icon:hover { background: #e5e7eb; }
</style>
