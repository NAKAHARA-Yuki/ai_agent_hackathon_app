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
    tasks: p.startsWith('/tasks')
  }
})

function go(name){ if(route.name!==name) router.push({ name }) }
</script>

<template>
  <nav class="footer-nav" aria-label="フッターナビゲーション">
  <button class="nav-item" :class="{active:active.home}" @click="go('main')" aria-label="ホーム (メインページ)">
      <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M3 11.5 12 4l9 7.5" />
        <path d="M5 10v10h5v-6h4v6h5V10" />
      </svg>
      <span class="label">ホーム</span>
    </button>
    <button class="nav-item" :class="{active:active.plan}" @click="go('travel-wizard')" aria-label="プラン">
      <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1 1 0 0 1 .2 1.1 8 8 0 0 1-14.2 0A1 1 0 0 1 5.6 15a8 8 0 0 1 0-6 1 1 0 0 1-.2-1.1 8 8 0 0 1 14.2 0 1 1 0 0 1-.2 1.1 8 8 0 0 1 0 6Z" />
      </svg>
      <span class="label">プラン</span>
    </button>
    <button class="nav-item" :class="{active:active.schedule}" @click="go('plans')" aria-label="旅行予定">
      <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
        <line x1="16" y1="2" x2="16" y2="6" />
        <line x1="8" y1="2" x2="8" y2="6" />
        <line x1="3" y1="10" x2="21" y2="10" />
        <path d="M8 14h.01" />
        <path d="M12 14h.01" />
        <path d="M16 14h.01" />
        <path d="M8 18h.01" />
        <path d="M12 18h.01" />
        <path d="M16 18h.01" />
      </svg>
      <span class="label">予定</span>
    </button>
    <button class="nav-item" :class="{active:active.tasks}" @click="go('tasks')" aria-label="タスク">
      <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M9 11l3 3L22 4" />
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
      </svg>
      <span class="label">タスク</span>
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
