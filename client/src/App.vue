<script setup>
import { RouterView, RouterLink, useRouter, useRoute } from 'vue-router'
import { computed, ref, onMounted, onUnmounted } from 'vue'
import FooterNav from '@/components/FooterNav.vue'
import SessionTimeoutWarning from '@/components/SessionTimeoutWarning.vue'
import { useAuthStore } from '@/stores/authStore'
import { useQuizStore } from '@/stores/quizStore'

const router = useRouter()
const auth = useAuthStore()
const quiz = useQuizStore()
const isAuthed = computed(() => auth.isAuthenticated)
const route = useRoute()
const showFooter = computed(() => {
  if(!isAuthed.value) return false
  const p = route.path
  return p === '/'
    || p.startsWith('/main')
    || p.startsWith('/travel-wizard')
    || p.startsWith('/tasks')
    || p.startsWith('/memories')
    || p.startsWith('/plans')
    || p.startsWith('/results')
    || p.startsWith('/chat')
})
const showMenu = ref(false)
const menuRoot = ref(null)
let removeAfterEach
const displayName = computed(() => auth.user?.name || auth.user?.user_id || '')
// セッション期限切れイベントハンドラ (remove用に参照保持)
let onAuthExpired = null

function logout() {
  auth.logout()
  try { quiz.resetQuiz() } catch {}
  router.replace({ name: 'login' })
}

function toggleMenu() {
  showMenu.value = !showMenu.value
}

function viewResults() {
  showMenu.value = false
  router.push({ name: 'results' })
}

async function redoDiagnosis() {
  showMenu.value = false
  try {
    await quiz.fetchQuestions()
    if (quiz.totalQuestions > 0) {
      quiz.resetQuiz()
      router.push({ name: 'question', params: { questionNumber: 1 } })
    } else {
      router.push({ name: 'home' })
    }
  } catch {
    router.push({ name: 'home' })
  }
}

function handleDocumentClick(e) {
  if (!showMenu.value) return
  const root = menuRoot.value
  if (root && !root.contains(e.target)) {
    showMenu.value = false
  }
}

onMounted(() => {
  removeAfterEach = router.afterEach(() => { showMenu.value = false })
  document.addEventListener('click', handleDocumentClick)
  onAuthExpired = (e) => {
    const redirect = e?.detail?.redirect || '/'
    router.replace({ name: 'login', query: { redirect, reason: 'expired' } })
  }
  window.addEventListener('auth:expired', onAuthExpired)
})

onUnmounted(() => {
  if (removeAfterEach) try { removeAfterEach() } catch {}
  document.removeEventListener('click', handleDocumentClick)
  if (onAuthExpired) window.removeEventListener('auth:expired', onAuthExpired)
})
</script>

<template>
  <div id="app-container">
    <header class="site-header">
      <div class="brand">
        <RouterLink class="brand-link" :to="{ name: 'main' }" aria-label="メインへ">いざ旅</RouterLink>
      </div>
      <nav class="nav">
        <span v-if="isAuthed && displayName" class="user-name" :title="displayName">{{ displayName }}</span>
        <div v-if="isAuthed" class="menu" ref="menuRoot">
          <button class="icon-btn" @click="toggleMenu" aria-label="メニュー" :aria-expanded="showMenu">
            <span class="bar"></span>
            <span class="bar"></span>
            <span class="bar"></span>
          </button>
          <transition name="drawer">
            <aside v-if="showMenu" class="drawer" role="menu" aria-label="メニュー">
              <div class="drawer-header">
                <div class="avatar" aria-hidden="true">👤</div>
                <div class="header-text">
                  <div class="name" :title="displayName">{{ displayName || 'ゲスト' }}</div>
                  <button class="mypage-row" @click="showMenu=false; router.push({ name: 'mypage' })">
                    <span class="row-left">📝 マイページ</span>
                    <span class="row-right">›</span>
                  </button>
                </div>
              </div>
              <div class="drawer-title subtle">診断結果</div>
              <button class="menu-item" role="menuitem" @click="viewResults">結果を閲覧</button>
              <button class="menu-item" role="menuitem" @click="redoDiagnosis">再診断</button>
              <hr class="divider" />
              <button class="menu-item danger" role="menuitem" @click="logout">ログアウト</button>
            </aside>
          </transition>
        </div>
      </nav>
    </header>
    <transition name="fade">
      <div v-if="showMenu" class="backdrop" @click="showMenu=false"></div>
    </transition>
    <main class="content">
      <RouterView />
    </main>
    <FooterNav v-if="showFooter" />
    <SessionTimeoutWarning v-if="isAuthed" />
  </div>
</template>

<style scoped>
#app-container { 
  display: flex; 
  flex-direction: column; 
  height: 100vh; 
  height: 100dvh; /* 動的ビューポート高さを使用 */
  overflow: hidden; 
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); 
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
}

.site-header { 
  width: 100%; 
  display: flex; 
  align-items: center; 
  justify-content: space-between; 
  padding: 8px calc(14px + env(safe-area-inset-right)) 8px calc(14px + env(safe-area-inset-left)); 
  background: rgba(255,255,255,0.7); 
  backdrop-filter: blur(6px); 
  box-shadow: 0 2px 10px rgba(0,0,0,0.05); 
  position: sticky; 
  top: 0; 
  z-index: 100; 
  box-sizing: border-box; 
  border-bottom: 1px solid rgba(0,0,0,0.04); 
  min-height: 56px; 
  flex-shrink: 0; /* ヘッダーの収縮を防ぐ */
}

/* モバイル対応: ヘッダーの調整 */
@media (max-width: 768px) {
  .site-header {
    padding: 10px calc(16px + env(safe-area-inset-right)) 10px calc(16px + env(safe-area-inset-left));
    min-height: 60px;
  }
}

@media (max-width: 480px) {
  .site-header {
    padding: 8px calc(12px + env(safe-area-inset-right)) 8px calc(12px + env(safe-area-inset-left));
  }
}
.brand { 
  font-weight: 700; 
  color:#1f2937; 
  flex: 1 1 auto; 
  min-width: 0; 
  overflow: hidden; 
  text-overflow: ellipsis; 
  white-space: nowrap; 
  font-size: 18px; /* フォントサイズを明示 */
}
.brand-link { 
  color: inherit; 
  text-decoration: none; 
  cursor: pointer; 
  display: inline-block; 
  padding: 4px 6px; 
  border-radius: 6px; 
}
.brand-link:hover { background: rgba(0,0,0,0.05); }

.nav { 
  display:flex; 
  align-items:center; 
  gap:10px; 
  position: relative; 
  flex: 0 0 auto; 
}
.nav .link { 
  background:transparent; 
  border:none; 
  color:#2563eb; 
  cursor:pointer; 
  font-size: 14px; 
}

.user-name { 
  color: var(--color-text); 
  font-weight: 600; 
  max-width: 40vw; 
  overflow: hidden; 
  text-overflow: ellipsis; 
  white-space: nowrap; 
}

/* モバイル対応: ブランドとナビの調整 */
@media (max-width: 768px) {
  .brand {
    font-size: 16px;
  }
  
  .user-name {
    max-width: 30vw;
    font-size: 14px;
  }
  
  .nav {
    gap: 8px;
  }
}

@media (max-width: 480px) {
  .brand {
    font-size: 15px;
  }
  
  .user-name {
    max-width: 25vw;
    font-size: 13px;
  }
}

.menu { position: relative; }
.icon-btn { width: 36px; height: 36px; border:1px solid rgba(0,0,0,0.06); background:rgba(255,255,255,0.6); cursor:pointer; padding: 6px; border-radius: 10px; display:flex; flex-direction: column; justify-content: center; align-items:center; gap:4px; margin-left: 6px; }
.icon-btn:hover { background: rgba(0,0,0,0.05); }
.bar { display:block; width: 18px; height: 2px; background:#1f2937; border-radius: 2px; }

.drawer {
  position: fixed; right: 0; top: 0; height: 100vh; width: min(88vw, 320px); background: #ffffff;
  color: var(--color-text); border-left: 1px solid rgba(0,0,0,0.08); box-shadow: -10px 0 30px rgba(0,0,0,0.12);
  padding: 14px; padding-top: calc(14px + env(safe-area-inset-top)); padding-bottom: calc(14px + env(safe-area-inset-bottom));
  z-index: 110; display: flex; flex-direction: column; gap: 6px; overflow-y: auto; overscroll-behavior: contain; -webkit-overflow-scrolling: touch;
}
.drawer-title { font-size: 13px; font-weight: 700; color:#374151; padding: 6px 6px; letter-spacing: 0.2px; }
.drawer-title.subtle { color:#6b7280; font-weight: 600; }
.menu-item { width:100%; text-align:left; background:transparent; color: var(--color-text); border:none; padding:12px 10px; border-radius: 8px; cursor:pointer; font-size: 15px; }
.menu-item:hover { background: #eff6ff; }
.menu-item.danger { color:#b91c1c; }
.divider { border: none; border-top: 1px solid rgba(0,0,0,0.06); margin: 10px 0; }

.drawer-header { display:flex; align-items:center; gap:10px; padding: 6px 4px 10px; border-bottom: 1px solid #f3f4f6; margin-bottom: 8px; }
.avatar { width: 36px; height: 36px; display:grid; place-items:center; border-radius: 50%; background:#eef2ff; font-size: 18px; }
.header-text { display:flex; flex-direction:column; min-width: 0; }
.header-text .name { font-weight: 700; color: var(--color-text); max-width: 210px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mypage-row { margin-top: 6px; display:flex; align-items:center; justify-content:space-between; width:100%; background:#f9fafb; border:1px solid #eef2ff; color:#1f2937; padding:8px 10px; border-radius:8px; cursor:pointer; font-size: 14px; }
.mypage-row:hover { background:#eef2ff; }
.mypage-row .row-left { display:flex; align-items:center; gap:6px; }
.mypage-row .row-right { color:#6b7280; font-weight:700; }

.backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.35); backdrop-filter: blur(1px); z-index: 90; }

/* ドロワーのスライドアニメ（不透明のまま） */
.drawer-enter-active, .drawer-leave-active { transition: transform .25s ease; }
.drawer-enter-from, .drawer-leave-to { transform: translateX(100%); }
.drawer-enter-to, .drawer-leave-from { transform: translateX(0); }

/* 背景フェード */
.fade-enter-active, .fade-leave-active { transition: opacity .2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.divider { border: none; border-top: 1px solid rgba(0,0,0,0.08); margin: 8px 0; }

.content { 
  flex: 1 1 auto; 
  display: flex; 
  align-items: stretch; 
  justify-content: flex-start; 
  padding: 16px; 
  overflow: auto; 
  min-height: 0; 
  -webkit-overflow-scrolling: touch; /* スムーズなスクロール */
  overscroll-behavior: contain; /* バウンス防止 */
}


/* travel-wizard では全面表示のため padding を除去 */
:deep(.route-travel-wizard) .content, :deep(.content:has(> .wizard-wrap)) { padding:0; }
/* travel-wizard では外側スクロールも抑止 */
:deep(.content:has(> .wizard-wrap)) { overflow:hidden; }

/* チャット画面では外側のスクロールを抑止し、ビュー内でスクロールさせる */
:deep(.content:has(> .general-chat)) { overflow: hidden; padding-bottom: 0; }

/* モバイルでの全画面対応 */
@media (max-width: 768px) {
  .content { 
    padding: 8px; 
    justify-content: center; 
    align-items: center;
    /* travel-wizardなど特定のビューでは調整 */
  }
  
  /* travel-wizard以外のビューでのパディング調整 */
  :deep(.content:not(:has(> .wizard-wrap))) {
    padding: 8px;
    align-items: flex-start; /* 上寄せに変更 */
  }
}

/* 非常に小さな画面での追加調整 */
@media (max-width: 480px) {
  .content {
    padding: 4px;
  }
  
  :deep(.content:not(:has(> .wizard-wrap))) {
    padding: 4px;
  }
}
</style>
