<script setup>
import { RouterView, useRouter } from 'vue-router'
import { computed } from 'vue'
import { useAuthStore } from '@/stores/authStore'
import { useQuizStore } from '@/stores/quizStore'

const router = useRouter()
const auth = useAuthStore()
const quiz = useQuizStore()
const isAuthed = computed(() => auth.isAuthenticated)

function logout() {
  auth.logout()
  try { quiz.resetQuiz() } catch {}
  router.replace({ name: 'login' })
}
</script>

<template>
  <div id="app-container">
    <header class="site-header">
      <div class="brand" @click="router.push({ name: 'home' })" role="button">Travel Quiz</div>
      <nav class="nav">
        <button v-if="isAuthed" class="link" @click="logout">ログアウト</button>
      </nav>
    </header>
    <RouterView />
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

.site-header { width:100%; display:flex; align-items:center; justify-content:space-between; padding:12px 16px; background: rgba(255,255,255,0.7); backdrop-filter: blur(6px); box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
.brand { font-weight: 700; color:#1f2937; cursor:pointer; }
.nav .link { background:transparent; border:none; color:#2563eb; cursor:pointer; font-size: 14px; }
</style>
