<script setup>
import { useRouter } from 'vue-router'

const props = defineProps({
  label: { type: String, default: '戻る' },
  fallbackName: { type: String, default: 'home' },
  fallbackTo: { type: [Object, String], default: null }
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
  <button class="back-btn" type="button" @click="goBack" aria-label="戻る">
    ← {{ label }}
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
  margin-bottom: 10px;
}
.back-btn:hover { background: #f3f4f6; }
</style>
