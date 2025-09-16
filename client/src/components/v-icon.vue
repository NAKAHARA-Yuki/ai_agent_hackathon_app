<script setup>
import { computed } from 'vue'

const props = defineProps({
  name: { type: String, required: true }, // e.g. 'chat', 'chat-outline', 'mdi-chat'
  size: { type: [Number, String], default: 20 },
  color: { type: String, default: 'currentColor' },
  ariaLabel: { type: String, default: '' },
})

const sizePx = computed(() => (typeof props.size === 'number' ? `${props.size}px` : props.size))
const ariaLabel = computed(() => props.ariaLabel || props.name)
const normalized = computed(() => props.name.startsWith('mdi-') ? props.name : `mdi-${props.name}`)
const classes = computed(() => `mdi ${normalized.value}`)
</script>

<template>
  <i :class="classes" :style="{ fontSize: sizePx, color: color, lineHeight: 1 }" role="img" :aria-label="ariaLabel"></i>
</template>

<style scoped>
i { display: inline-block; vertical-align: middle; }
</style>
