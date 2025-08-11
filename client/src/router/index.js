import { createRouter, createWebHistory } from 'vue-router'
import StartView from '../views/StartView.vue'
import QuestionView from '../views/QuestionView.vue'
import ResultView from '../views/ResultView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
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

export default router
