<template>
  <div class="wizard-screen bg-gradient-to-b from-white to-slate-50 text-slate-900 p-4 pb-4">
    <h1 class="text-center text-xl font-bold my-2 tracking-tight">旅行プランのご提案</h1>
    <p class="text-center text-slate-500 text-sm mb-4">気になるプランを選択してください</p>
  <div class="wizard-scroll space-y-3 max-w-xl mx-auto pb-16 pb-safe overscroll-contain">
      <div
        v-for="plan in plans"
        :key="plan.id"
        @click="$emit('select-plan', plan)"
        class="rounded-xl p-4 bg-white ring-1 ring-slate-200 shadow-sm cursor-pointer active:scale-[0.985] transition hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        tabindex="0"
        @keydown.enter.prevent="$emit('select-plan', plan)"
      >
        <h2 class="font-semibold text-base mb-1 leading-snug">{{ plan.title }}</h2>
        <p class="text-xs text-slate-500">{{ plan.tags }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({ plans: { type: Array, default: () => [] } })
defineEmits(['select-plan'])
</script>
