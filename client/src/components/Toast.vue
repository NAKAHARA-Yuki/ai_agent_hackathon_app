<template>
  <transition name="toast-fade">
    <div v-if="visible" class="toast" :class="type" role="status" aria-live="polite">
      {{ message }}
    </div>
  </transition>
</template>

<script setup>
import { ref, watchEffect, onUnmounted } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  type: { type: String, default: 'info' },
  duration: { type: Number, default: 3000 }
})
const emit = defineEmits(['update:modelValue'])
const visible = ref(false)
const message = ref('')
let timer = null

watchEffect(() => {
  if (props.modelValue) {
    message.value = props.modelValue
    visible.value = true
    clearTimeout(timer)
    timer = setTimeout(() => {
      visible.value = false
      emit('update:modelValue', '')
    }, props.duration)
  }
})

onUnmounted(() => { clearTimeout(timer) })
</script>

<style scoped>
.toast { position:fixed; left:50%; bottom: calc(20px + env(safe-area-inset-bottom)); transform:translateX(-50%); background: var(--color-text); color:#fff; padding:12px 16px; border-radius:16px; font-size:14px; font-weight:600; box-shadow:0 8px 24px rgba(0,0,0,0.25); max-width:calc(100vw - 32px); text-align:center; }
.toast.success { background: var(--color-success); }
.toast.error { background: var(--color-danger); }
.toast.info { background: var(--color-primary); }
.toast-fade-enter-active,.toast-fade-leave-active { transition: opacity .25s, transform .25s; }
.toast-fade-enter-from,.toast-fade-leave-to { opacity:0; transform: translate(-50%, 20px); }
</style>
