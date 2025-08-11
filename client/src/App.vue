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
          <div v-if="showMenu" class="menu-panel" role="menu">
            <div class="menu-section">
              <div class="menu-title">診断結果</div>
              <button class="menu-item" role="menuitem" @click="viewResults">結果を閲覧</button>
              <button class="menu-item" role="menuitem" @click="redoDiagnosis">再診断</button>
      <hr class="divider" />
      <button class="menu-item" role="menuitem" @click="logout">ログアウト</button>
            </div>
          </div>
        </div>
      </nav>
    </header>
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

.menu-panel {
  position: absolute; right: 0; top: 40px; min-width: 200px; background:#fff; border:1px solid rgba(0,0,0,0.08);
  border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.12); padding: 10px; z-index: 20;
}
.menu-title { font-size: 12px; color:#6b7280; padding: 6px 8px; }
.menu-item { width:100%; text-align:left; background:transparent; border:none; padding:10px 8px; border-radius: 8px; cursor:pointer; }
.menu-item:hover { background: rgba(37,99,235,0.08); }
.divider { border: none; border-top: 1px solid rgba(0,0,0,0.08); margin: 8px 0; }

.content {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px 16px;
}
</style>
