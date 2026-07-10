import { create } from 'zustand';
import { Plan } from '../services/apiClient';

interface ActivePlanState {
  activePlan: Plan | null;
  loading: boolean;
  error: string;
  
  fetchActivePlan: (authHeader: Record<string, string>) => Promise<Plan | null>;
  activatePlan: (planId: string, authHeader: Record<string, string>) => Promise<Plan | null>;
  deactivatePlan: (authHeader: Record<string, string>) => Promise<boolean>;
  togglePlan: (planId: string, authHeader: Record<string, string>) => Promise<any>;
  clearActivePlan: () => void;
}

const API_BASE = '/api';

export const useActivePlanStore = create<ActivePlanState>((set, get) => ({
  activePlan: null,
  loading: false,
  error: '',

  async fetchActivePlan(authHeader) {
    set({ loading: true, error: '' });
    try {
      const response = await fetch(`${API_BASE}/active-plan`, {
        headers: {
          'Content-Type': 'application/json',
          ...authHeader,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      set({ activePlan: data.active_plan });
      return data.active_plan;
    } catch (e) {
      set({ error: 'アクティブプランの読み込みに失敗しました' });
      console.error('Failed to fetch active plan:', e);
      return null;
    } finally {
      set({ loading: false });
    }
  },

  async activatePlan(planId, authHeader) {
    if (!planId) {
      throw new Error('Plan ID is required');
    }

    set({ loading: true, error: '' });
    try {
      const response = await fetch(`${API_BASE}/active-plan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeader,
        },
        body: JSON.stringify({ plan_id: planId }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      set({ activePlan: data.active_plan });
      return data.active_plan;
    } catch (e) {
      set({ error: 'プランの有効化に失敗しました' });
      console.error('Failed to activate plan:', e);
      throw e;
    } finally {
      set({ loading: false });
    }
  },

  async deactivatePlan(authHeader) {
    set({ loading: true, error: '' });
    try {
      const response = await fetch(`${API_BASE}/active-plan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeader,
        },
        body: JSON.stringify({ plan_id: null }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      set({ activePlan: null });
      return true;
    } catch (e) {
      set({ error: 'プランの無効化に失敗しました' });
      console.error('Failed to deactivate plan:', e);
      throw e;
    } finally {
      set({ loading: false });
    }
  },

  async togglePlan(planId, authHeader) {
    const current = get().activePlan;
    if (current && current.id === planId) {
      return await get().deactivatePlan(authHeader);
    } else {
      return await get().activatePlan(planId, authHeader);
    }
  },

  clearActivePlan() {
    set({ activePlan: null, error: '', loading: false });
  },
}));
