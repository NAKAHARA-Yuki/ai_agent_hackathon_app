<script setup>
import { RouterView, useRouter } from 'vue-router'
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/authStore'
import { useQuizStore } from '@/stores/quizStore'

const router = useRouter()
const auth = useAuthStore()
const quiz = useQuizStore()
const isAuthed = computed(() => auth.isAuthenticated)
const showMenu = ref(false)
const menuRoot = ref(null)
let removeAfterEach

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
  // ルート遷移時は常にメニューを閉じる
  removeAfterEach = router.afterEach(() => { showMenu.value = false })
  // 外側クリックでメニューを閉じる
  document.addEventListener('click', handleDocumentClick)
})

onUnmounted(() => {
  if (removeAfterEach) try { removeAfterEach() } catch {}
  document.removeEventListener('click', handleDocumentClick)
})
</script>

<template>
  <div id="app-container">
    <header class="site-header">
  <div class="brand" @click="router.push({ name: 'main' })" role="button">いざ旅</div>
      <nav class="nav">
        <div v-if="isAuthed" class="menu" ref="menuRoot">
          <button class="icon-btn" @click="toggleMenu" aria-label="メニュー" :aria-expanded="showMenu">
            <span class="bar"></span>
            <span class="bar"></span>
            <span class="bar"></span>
          </button>
          <transition name="drawer">
            <aside v-if="showMenu" class="drawer" role="menu" aria-label="メニュー">
              <div class="drawer-title">診断結果</div>
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
  </div>
</template>

<style scoped>
#app-container {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

.site-header { width:100%; display:flex; align-items:center; justify-content:space-between; padding:12px 16px; background: rgba(255,255,255,0.7); backdrop-filter: blur(6px); box-shadow: 0 2px 10px rgba(0,0,0,0.05); position:relative; z-index: 10; }
.brand { font-weight: 700; color:#1f2937; cursor:pointer; }
.nav { display:flex; align-items:center; gap:10px; position: relative; }
.nav .link { background:transparent; border:none; color:#2563eb; cursor:pointer; font-size: 14px; }

.menu { position: relative; }
.icon-btn {
  width: 36px; height: 32px; border:none; background:transparent; cursor:pointer; padding: 4px; border-radius: 8px;
  display:flex; flex-direction: column; justify-content: center; gap:4px;
}
.icon-btn:hover { background: rgba(0,0,0,0.05); }
.bar { display:block; width: 20px; height: 2px; background:#1f2937; border-radius: 2px; }

.drawer {
  position: fixed; right: 0; top: 0; height: 100vh; width: 280px; background: #ffffff;
  color: #111827; border-left: 1px solid rgba(0,0,0,0.08); box-shadow: -10px 0 30px rgba(0,0,0,0.12);
  padding: 14px; z-index: 50; display: flex; flex-direction: column; gap: 6px;
}
.drawer-title { font-size: 14px; font-weight: 700; color:#374151; padding: 8px 6px; }
.menu-item { width:100%; text-align:left; background:transparent; color:#111827; border:none; padding:12px 10px; border-radius: 8px; cursor:pointer; font-size: 15px; }
.menu-item:hover { background: #eff6ff; }
.menu-item.danger { color:#b91c1c; }
.divider { border: none; border-top: 1px solid rgba(0,0,0,0.08); margin: 8px 0; }

.backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.35); backdrop-filter: blur(1px); z-index: 40; }

/* ドロワーのスライドアニメ */
.drawer-enter-active, .drawer-leave-active { transition: transform .25s ease, opacity .2s ease; }
.drawer-enter-from, .drawer-leave-to { transform: translateX(100%); opacity: 0.8; }
.drawer-enter-to, .drawer-leave-from { transform: translateX(0); opacity: 1; }

/* 背景フェード */
.fade-enter-active, .fade-leave-active { transition: opacity .2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.divider { border: none; border-top: 1px solid rgba(0,0,0,0.08); margin: 8px 0; }

.content {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px 16px;
}
</style>
