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
      <v-icon v-if="icon === 'home'" name="home" :size="18" aria-label="ホーム" />
      <v-icon v-else name="chevron-left" :size="18" aria-label="戻る" />
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
  color: var(--color-text);
  border-radius: 10px;
  padding: 6px 10px;
  font-weight: 600;
  cursor: pointer;
}
.back-btn:hover { background: #f8fafc; }

.back-btn.icon {
  width: 36px;
  height: 36px;
  display: inline-grid;
  place-items: center;
  border-radius: 10px;
  padding: 0;
  transition: background 0.2s ease;
}
.back-btn.icon:hover { background: #eef2f7; }
</style>
