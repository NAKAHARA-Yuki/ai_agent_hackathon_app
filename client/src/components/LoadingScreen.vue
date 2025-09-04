<template>
  <div class="wizard-screen flex flex-col items-center justify-center h-full bg-gradient-to-b from-white to-slate-50 text-slate-700 p-6 pb-safe">
    <div class="text-lg font-semibold mb-2 tracking-tight">AIが旅行プランを生成中...</div>
    <div class="text-xs text-slate-500 mb-10">最適なプランを考えています。少しお待ちください。</div>
    <div class="relative w-40 h-40 flex items-center justify-center">
      <div class="absolute inset-0 animate-pulse rounded-full bg-blue-100"></div>
      <div class="animate-spin rounded-full h-24 w-24 border-4 border-blue-200 border-t-blue-600"></div>
    </div>
  </div>
</template>

<script setup>
</script>
