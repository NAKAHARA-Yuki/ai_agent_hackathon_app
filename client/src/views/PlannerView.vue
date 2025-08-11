<script setup>
import { ref } from 'vue'
import ChatPanel from '@/components/ChatPanel.vue'
import MapPanel from '@/components/MapPanel.vue'

// エージェントが提案した場所の一覧（{ name, lat, lng, note }）
const places = ref([])

// チャットの送信イベントでエージェント応答と場所候補を反映
function handleAgentUpdate(payload) {
  // payload: { reply: string, places?: Array<{name, lat, lng, note?}> }
  if (Array.isArray(payload?.places)) {
    // 軽いバリデーション
    places.value = payload.places
      .filter(p => typeof p?.lat === 'number' && typeof p?.lng === 'number')
      .slice(0, 50)
  }
}
</script>

<template>
  <main class="planner">
    <section class="left">
      <ChatPanel @agent-update="handleAgentUpdate" />
    </section>
    <section class="right">
      <MapPanel :places="places" />
    </section>
  </main>
  
</template>

<style scoped>
.planner {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr;
  gap: 12px;
  height: calc(100vh - 80px);
  padding: 12px;
}
.left, .right {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 6px 18px rgba(0,0,0,.08);
  overflow: hidden;
  height: 100%;
}
.left { display:flex; }
.right { position: relative; }

@media (max-width: 960px) {
  .planner { grid-template-columns: 1fr; height: auto; }
  .right { height: 480px; }
}
</style>
