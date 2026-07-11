import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useAuthStore } from './authStore'

const API_BASE = '/api'

export const useActivePlanStore = defineStore('activePlan', () => {
  const activePlan = ref(null)
  const loading = ref(false)
  const error = ref('')
  
  const auth = useAuthStore()

  const isActive = computed(() => !!activePlan.value)
  const activePlanId = computed(() => activePlan.value?.id || null)
  const activePlanTitle = computed(() => activePlan.value?.title || '')

  // Fetch currently active plan
  async function fetchActivePlan() {
    loading.value = true
    error.value = ''
    try {
      const response = await fetch(`${API_BASE}/active-plan`, {
        headers: {
          'Content-Type': 'application/json',
          ...auth.authHeader()
        }
      })
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      
      const data = await response.json()
      activePlan.value = data.active_plan
      return data.active_plan
    } catch (e) {
      error.value = 'アクティブプランの読み込みに失敗しました'
      console.error('Failed to fetch active plan:', e)
      return null
    } finally {
      loading.value = false
    }
  }

  // Activate a plan
  async function activatePlan(planId) {
    if (!planId) {
      throw new Error('Plan ID is required')
    }
    
    loading.value = true
    error.value = ''
    try {
      const response = await fetch(`${API_BASE}/active-plan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...auth.authHeader()
        },
        body: JSON.stringify({ plan_id: planId })
      })
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      
      const data = await response.json()
      activePlan.value = data.active_plan
      return data.active_plan
    } catch (e) {
      error.value = 'プランの有効化に失敗しました'
      console.error('Failed to activate plan:', e)
      throw e
    } finally {
      loading.value = false
    }
  }

  // Deactivate current plan
  async function deactivatePlan() {
    loading.value = true
    error.value = ''
    try {
      const response = await fetch(`${API_BASE}/active-plan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...auth.authHeader()
        },
        body: JSON.stringify({ plan_id: null })
      })
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      
      activePlan.value = null
      return true
    } catch (e) {
      error.value = 'プランの無効化に失敗しました'
      console.error('Failed to deactivate plan:', e)
      throw e
    } finally {
      loading.value = false
    }
  }

  // Toggle plan activation status
  async function togglePlan(planId) {
    if (activePlanId.value === planId) {
      return await deactivatePlan()
    } else {
      return await activatePlan(planId)
    }
  }

  // Clear store state (useful for logout)
  function clearActivePlan() {
    activePlan.value = null
    error.value = ''
    loading.value = false
  }

  return {
    // State
    activePlan,
    loading,
    error,
    
    // Computed
    isActive,
    activePlanId,
    activePlanTitle,
    
    // Actions
    fetchActivePlan,
    activatePlan,
    deactivatePlan,
    togglePlan,
    clearActivePlan
  }
})