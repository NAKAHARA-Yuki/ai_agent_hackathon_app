<script setup>
import { useRoute, useRouter } from 'vue-router'
import { computed } from 'vue'
const route = useRoute()
const router = useRouter()

const active = computed(() => {
  const p = route.path || ''
  return {
    home: p.startsWith('/main'),
    plan: p.startsWith('/travel-wizard'),
    schedule: p.startsWith('/plans'),
  memories: p.startsWith('/memories') || p.startsWith('/tasks')
  }
})

function go(name){ if(route.name!==name) router.push({ name }) }
</script>

<template>
  <nav class="footer-nav" aria-label="フッターナビゲーション">
  <button class="nav-item" :class="{active:active.home}" @click="go('main')" aria-label="ホーム (メインページ)">
  <v-icon class="icon" name="home" :size="22" aria-label="ホーム" />
      <span class="label">ホーム</span>
    </button>
    <button class="nav-item" :class="{active:active.plan}" @click="go('travel-wizard')" aria-label="プラン">
  <v-icon class="icon" name="wallet-travel" :size="22" aria-label="プラン" />
      <span class="label">プラン</span>
    </button>
    <button class="nav-item" :class="{active:active.schedule}" @click="go('plans')" aria-label="旅行予定">
  <v-icon class="icon" name="calendar" :size="22" aria-label="旅行予定" />
      <span class="label">予定</span>
    </button>
  <button class="nav-item" :class="{active:active.memories}" @click="go('memories')" aria-label="思い出">
  <v-icon class="icon" name="image-multiple" :size="22" aria-label="思い出" />
      <span class="label">思い出</span>
    </button>
  </nav>
</template>

<style scoped>
.footer-nav { 
  width: 100%; 
  display: flex; 
  justify-content: space-between; 
  align-items: stretch; 
  background: rgba(255,255,255,0.95); 
  backdrop-filter: blur(12px); 
  border-top: 1px solid rgba(0,0,0,0.08); 
  padding: 0 0 env(safe-area-inset-bottom); 
  box-sizing: border-box; 
  box-shadow: 0 -2px 8px rgba(0,0,0,0.08); 
  position: sticky; 
  bottom: 0; 
  z-index: 100;
  flex-shrink: 0;
}

.nav-item { 
  flex: 1 1 0; 
  background: transparent; 
  border: none; 
  padding: 6px 4px 4px; 
  border-radius: 0; 
  display: flex; 
  flex-direction: column; 
  align-items: center; 
  justify-content: center; 
  gap: 2px; 
  color: var(--color-text-subtle); 
  font-size: 11px; 
  font-weight: 600; 
  letter-spacing: .3px; 
  cursor: pointer; 
  position: relative; 
  min-height: 56px; 
}

.nav-item .icon { width: 22px; height: 22px; }

.nav-item.active { 
  color: var(--color-primary); 
  background: linear-gradient(to top, #eef4ff, rgba(238,244,255,0)); 
}

.nav-item:not(.active):hover { background: rgba(0,0,0,0.05); }

.nav-item:active { transform: translateY(1px); }

/* モバイルでのタッチフレンドリーな調整 */
@media (max-width: 768px) {
  .nav-item {
    min-height: 60px;
    padding: 8px 4px 6px;
  }
  
  .nav-item .icon {
    width: 24px;
    height: 24px;
  }
  
  .nav-item {
    font-size: 12px;
  }
}
</style>
