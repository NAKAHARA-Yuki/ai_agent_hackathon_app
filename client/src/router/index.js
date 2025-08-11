import { createRouter, createWebHistory } from 'vue-router'
import StartView from '../views/StartView.vue'
import AuthView from '../views/AuthView.vue'
import { useAuthStore } from '@/stores/authStore'
import QuestionView from '../views/QuestionView.vue'
import ResultView from '../views/ResultView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/auth',
      name: 'auth',
      component: AuthView
    },
    {
      path: '/',
      name: 'home',
  component: StartView
    },
    {
      path: '/question/:questionNumber',
      name: 'question',
      component: QuestionView
    },
    {
      path: '/results',
      name: 'results',
      component: ResultView
    }
  ]
})

// 認証ガード: 未認証なら /auth へ
router.beforeEach((to) => {
  const auth = useAuthStore()
  const publicPaths = new Set(['/auth'])
  if (!auth.isAuthenticated && !publicPaths.has(to.path)) {
    return { name: 'auth', query: { redirect: to.fullPath } }
  }
  if (auth.isAuthenticated && to.name === 'auth') {
    return { name: 'home' }
  }
})

export default router
