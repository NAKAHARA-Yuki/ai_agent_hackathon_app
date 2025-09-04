<template>
  <div class="wizard-screen bg-gradient-to-b from-white to-slate-50 text-slate-900 p-4 pb-4">
  <div class="wizard-scroll max-w-xl mx-auto pb-24 pb-safe overscroll-contain">
      <button
        @click="$emit('go-back')"
        class="text-sm text-slate-500 hover:text-slate-700 flex items-center gap-1 mb-2 active:translate-x-[-2px] transition"
      >
        ← 戻る
      </button>
      <h1 class="text-xl font-bold tracking-tight leading-tight mb-1">{{ plan.title }}</h1>
      <p class="text-xs text-slate-500 mb-4">タグ: {{ plan.tags }}</p>
      <section aria-labelledby="itinerary-heading" class="bg-white rounded-xl ring-1 ring-slate-200 shadow-sm p-4">
        <h2 id="itinerary-heading" class="font-semibold text-sm mb-2 text-slate-700">日程</h2>
        <ul class="list-disc pl-5 space-y-1 text-sm text-slate-700">
          <li v-for="(item, idx) in (plan.itinerary || [])" :key="idx">{{ item }}</li>
        </ul>
        <p v-if="!plan.itinerary || plan.itinerary.length===0" class="text-xs text-slate-400">日程データがありません</p>
      </section>
      <div class="pt-6">
        <button
          @click="$emit('confirm', plan)"
          class="w-full bg-blue-600 hover:bg-blue-500 active:bg-blue-700 font-semibold py-3 rounded-full text-white shadow-sm active:scale-[0.985] transition focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          このプランを確定する
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
// 旧コンテンツを全面置換済み
defineProps({
  plan: {
    type: Object,
    required: true,
    default: () => ({ title: '', tags: '', itinerary: [] })
  }
})
</script>

<style scoped>
</style>
