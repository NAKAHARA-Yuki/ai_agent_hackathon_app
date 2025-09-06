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
import PlannerView from '../views/PlannerView.vue'
import PlansListView from '../views/PlansListView.vue'
import TravelPlanWizardView from '../views/TravelPlanWizardView.vue'
import InterestsView from '../views/InterestsView.vue'
import TasksView from '../views/TasksView.vue'
import ScheduleView from '../views/ScheduleView.vue'
import PlanDetailView from '../views/PlanDetailView.vue'

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
      path: '/interests',
      name: 'interests',
      component: InterestsView
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
    },
  // 旧プランナー: travel-wizard へリダイレクト
  { path: '/planner', redirect: '/travel-wizard' },
  { path: '/plans', name: 'plans', component: PlansListView }
  ,{ path: '/travel-wizard', name: 'travel-wizard', component: TravelPlanWizardView }
  ,{ path: '/tasks', name: 'tasks', component: TasksView }
  ,{ path: '/schedule', name: 'schedule', component: ScheduleView }
  ,{ path: '/plans/:id', name: 'plan-detail', component: PlanDetailView }
  ]
})

// 認証ガード: 未認証なら /login へ、期限切れトークンも処理
router.beforeEach((to) => {
  const auth = useAuthStore()
  const publicPaths = new Set(['/login', '/signup', '/processing'])
  
  // トークンの期限をチェック（期限切れなら自動ログアウト）
  if (auth.checkAndCleanExpiredToken()) {
    // 期限切れでログアウトした場合、パブリックパス以外ならリダイレクト
    if (!publicPaths.has(to.path)) {
      return { name: 'login', query: { redirect: to.fullPath, reason: 'expired' } }
    }
  }
  
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
