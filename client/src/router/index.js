import { createRouter, createWebHistory } from 'vue-router'
import StartView from '../views/StartView.vue'
import MainView from '../views/MainView.vue'
import LoginView from '../views/LoginView.vue'
import SignupView from '../views/SignupView.vue'
import ProcessingView from '../views/ProcessingView.vue'
import { useAuthStore } from '@/stores/authStore'
import QuestionView from '../views/QuestionView.vue'
import ResultView from '../views/ResultView.vue'
import MyPageView from '../views/MyPageView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
  { path: '/login', name: 'login', component: LoginView },
  { path: '/signup', name: 'signup', component: SignupView },
  { path: '/processing', name: 'processing', component: ProcessingView },
    {
      path: '/',
      name: 'home',
  component: StartView
    },
    {
      path: '/main',
      name: 'main',
      component: MainView
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
    },
    {
      path: '/me',
      name: 'mypage',
      component: MyPageView
    }
  ]
})

// 認証ガード: 未認証なら /auth へ
router.beforeEach((to) => {
  const auth = useAuthStore()
  const publicPaths = new Set(['/login', '/signup', '/processing'])
  if (!auth.isAuthenticated && !publicPaths.has(to.path)) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (auth.isAuthenticated && (to.name === 'login' || to.name === 'signup')) {
    return { name: 'home' }
  }
  // すでに診断済みでトップに来たらメインへ
  if (auth.isAuthenticated && to.name === 'home' && auth.user?.diagnosis_completed) {
    return { name: 'main' }
  }
})

export default router
