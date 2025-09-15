import {
  agentChat,
  listPlans,
  createPlan,
  mapsKey,
  getActivePlan,
  setActivePlan,
  planDetail,
  deletePlan,
  isMock,
  __setMockEnv
} from './__mocks__/apiClient.js'

// Mock fetch globally
global.fetch = jest.fn()

describe('apiClient', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    global.localStorage.clear()
    // Reset mock environment
    __setMockEnv({ VITE_USE_MOCK: 'false' })
  })

  describe('agentChat', () => {
    it('should call agent chat API in non-mock mode', async () => {
      const mockResponse = { reply: 'Test reply', places: [], route_info: null, citations: [] }
      fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse)
      })

      const result = await agentChat({
        message: 'Hello',
        user_id: 'test-user',
        session_id: 'test-session',
        authHeader: { Authorization: 'Bearer token' }
      })

      expect(fetch).toHaveBeenCalledWith('/api/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer token' },
        body: JSON.stringify({ message: 'Hello', user_id: 'test-user', session_id: 'test-session' })
      })
      expect(result).toEqual(mockResponse)
    })

    it('should return mock response in mock mode', async () => {
      __setMockEnv({ VITE_USE_MOCK: 'true' })
      
      const result = await agentChat({ message: 'Hello' })
      
      expect(result).toHaveProperty('reply')
      expect(result).toHaveProperty('places')
      expect(result.reply).toContain('Hello')
    })

    it('should handle 401 unauthorized error', async () => {
      fetch.mockResolvedValueOnce({
        ok: false,
        status: 401
      })

      await expect(agentChat({
        message: 'Hello',
        user_id: 'test-user',
        session_id: 'test-session'
      })).rejects.toThrow('認証の有効期限が切れました。再度ログインしてください。')
    })

    it('should handle 503 service unavailable with retry', async () => {
      // First call returns 503, second call succeeds
      fetch.mockResolvedValueOnce({
        ok: false,
        status: 503
      }).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ reply: 'Success after retry', places: [] })
      })

      const result = await agentChat({
        message: 'Hello',
        user_id: 'test-user',
        session_id: 'test-session'
      })

      expect(fetch).toHaveBeenCalledTimes(2)
      expect(result.reply).toBe('Success after retry')
    })

    it('should fail after max retries on 503', async () => {
      // All calls return 503
      fetch.mockResolvedValue({
        ok: false,
        status: 503
      })

      await expect(agentChat({
        message: 'Hello',
        user_id: 'test-user',
        session_id: 'test-session'
      })).rejects.toThrow('HTTP 503')

      expect(fetch).toHaveBeenCalledTimes(4) // Initial + 3 retries
    })
  })

  describe('listPlans', () => {
    it('should list plans from API', async () => {
      const mockPlans = {
        items: [
          { id: '1', title: 'Plan 1', created_at: '2023-01-01T00:00:00Z', updated_at: '2023-01-01T00:00:00Z' }
        ]
      }
      fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockPlans)
      })

      const result = await listPlans({ Authorization: 'Bearer token' })

      expect(fetch).toHaveBeenCalledWith('/api/plans', {
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer token' }
      })
      expect(result).toEqual(mockPlans)
    })

    it('should handle mock mode for listPlans', async () => {
      __setMockEnv({ VITE_USE_MOCK: 'true' })
      
      // Set up mock plans in localStorage
      const mockPlans = [
        { id: '1', title: 'Mock Plan', created_at: '2023-01-01T00:00:00Z', updated_at: '2023-01-01T00:00:00Z' }
      ]
      global.localStorage.getItem.mockReturnValue(JSON.stringify(mockPlans))

      const result = await listPlans()
      
      expect(result.items).toHaveLength(1)
      expect(result.items[0].title).toBe('Mock Plan')
    })
  })

  describe('createPlan', () => {
    it('should create plan via API', async () => {
      const mockPlan = { id: 'new-plan', title: 'New Plan', status: 'confirmed' }
      fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockPlan)
      })

      const payload = { title: 'New Plan', text: 'Plan description' }
      const result = await createPlan(payload, { Authorization: 'Bearer token' })

      expect(fetch).toHaveBeenCalledWith('/api/plans', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer token' },
        body: JSON.stringify(payload)
      })
      expect(result).toEqual(mockPlan)
    })

    it('should handle createPlan in mock mode', async () => {
      __setMockEnv({ VITE_USE_MOCK: 'true' })
      
      const payload = { title: 'Mock Plan', text: 'Mock description' }
      const result = await createPlan(payload)

      expect(result).toHaveProperty('id')
      expect(result.title).toBe('Mock Plan')
      expect(result.text).toBe('Mock description')
      expect(global.localStorage.setItem).toHaveBeenCalled()
    })
  })

  describe('mapsKey', () => {
    it('should get maps key from API', async () => {
      const mockKey = { key: 'test-key', advanced: true, mapId: 'test-map-id' }
      fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockKey)
      })

      const result = await mapsKey()

      expect(fetch).toHaveBeenCalledWith('/api/maps-key')
      expect(result).toEqual(mockKey)
    })

    it('should return empty key on API error', async () => {
      fetch.mockResolvedValueOnce({
        ok: false,
        status: 500
      })

      const result = await mapsKey()
      expect(result).toEqual({ key: '', advanced: false, mapId: '' })
    })

    it('should return empty key in mock mode', async () => {
      __setMockEnv({ VITE_USE_MOCK: 'true' })
      
      const result = await mapsKey()
      expect(result).toEqual({ key: '', advanced: false, mapId: '' })
    })
  })

  describe('getActivePlan', () => {
    it('should get active plan from API', async () => {
      const mockResponse = { active_plan: { id: 'active-1', title: 'Active Plan' } }
      fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse)
      })

      const result = await getActivePlan({ Authorization: 'Bearer token' })

      expect(fetch).toHaveBeenCalledWith('/api/active-plan', {
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer token' }
      })
      expect(result).toEqual(mockResponse)
    })

    it('should get active plan from localStorage in mock mode', async () => {
      __setMockEnv({ VITE_USE_MOCK: 'true' })
      
      const mockActivePlan = { id: 'mock-active', title: 'Mock Active Plan' }
      global.localStorage.getItem.mockReturnValue(JSON.stringify(mockActivePlan))

      const result = await getActivePlan()
      expect(result.active_plan).toEqual(mockActivePlan)
    })
  })

  describe('setActivePlan', () => {
    it('should set active plan via API', async () => {
      const mockResponse = { active_plan: { id: 'plan-1' }, status: 'activated' }
      fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse)
      })

      const result = await setActivePlan('plan-1', { Authorization: 'Bearer token' })

      expect(fetch).toHaveBeenCalledWith('/api/active-plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer token' },
        body: JSON.stringify({ plan_id: 'plan-1' })
      })
      expect(result).toEqual(mockResponse)
    })

    it('should handle deactivation with null planId', async () => {
      const mockResponse = { active_plan: null, status: 'deactivated' }
      fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse)
      })

      const result = await setActivePlan(null, { Authorization: 'Bearer token' })
      expect(result).toEqual(mockResponse)
    })

    it('should set active plan in localStorage in mock mode', async () => {
      __setMockEnv({ VITE_USE_MOCK: 'true' })
      
      const mockPlans = [{ id: 'plan-1', title: 'Test Plan' }]
      global.localStorage.getItem.mockReturnValue(JSON.stringify(mockPlans))

      const result = await setActivePlan('plan-1')

      expect(result.active_plan).toEqual(mockPlans[0])
      expect(result.status).toBe('activated')
      expect(global.localStorage.setItem).toHaveBeenCalled()
    })

    it('should throw error for non-existent plan in mock mode', async () => {
      __setMockEnv({ VITE_USE_MOCK: 'true' })
      
      global.localStorage.getItem.mockReturnValue('[]')

      await expect(setActivePlan('non-existent')).rejects.toThrow('Plan not found')
    })
  })

  describe('planDetail', () => {
    it('should get plan detail from API', async () => {
      const mockPlan = { id: 'plan-1', title: 'Detailed Plan', text: 'Plan content' }
      fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockPlan)
      })

      const result = await planDetail('plan-1', { Authorization: 'Bearer token' })

      expect(fetch).toHaveBeenCalledWith('/api/plans/plan-1', {
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer token' }
      })
      expect(result).toEqual(mockPlan)
    })

    it('should get plan detail from localStorage in mock mode', async () => {
      __setMockEnv({ VITE_USE_MOCK: 'true' })
      
      const mockPlans = [{ id: 'plan-1', title: 'Mock Plan', text: 'Mock content' }]
      global.localStorage.getItem.mockReturnValue(JSON.stringify(mockPlans))

      const result = await planDetail('plan-1')
      expect(result).toEqual(mockPlans[0])
    })

    it('should throw error for non-existent plan in mock mode', async () => {
      __setMockEnv({ VITE_USE_MOCK: 'true' })
      
      global.localStorage.getItem.mockReturnValue('[]')

      await expect(planDetail('non-existent')).rejects.toThrow('Plan not found')
    })
  })

  describe('deletePlan', () => {
    it('should delete plan via API', async () => {
      const mockResponse = { status: 'deleted' }
      fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse)
      })

      const result = await deletePlan('plan-1', { Authorization: 'Bearer token' })

      expect(fetch).toHaveBeenCalledWith('/api/plans/plan-1', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer token' }
      })
      expect(result).toEqual(mockResponse)
    })

    it('should delete plan from localStorage in mock mode', async () => {
      __setMockEnv({ VITE_USE_MOCK: 'true' })
      
      const mockPlans = [
        { id: 'plan-1', title: 'Plan 1' },
        { id: 'plan-2', title: 'Plan 2' }
      ]
      global.localStorage.getItem.mockReturnValue(JSON.stringify(mockPlans))

      const result = await deletePlan('plan-1')

      expect(result.status).toBe('deleted')
      expect(global.localStorage.setItem).toHaveBeenCalledWith(
        'mockPlans',
        JSON.stringify([{ id: 'plan-2', title: 'Plan 2' }])
      )
    })

    it('should clear active plan if deleted plan was active in mock mode', async () => {
      __setMockEnv({ VITE_USE_MOCK: 'true' })
      
      const mockPlans = [{ id: 'plan-1', title: 'Plan 1' }]
      const mockActivePlan = { id: 'plan-1', title: 'Plan 1' }
      
      global.localStorage.getItem
        .mockReturnValueOnce(JSON.stringify(mockPlans))
        .mockReturnValueOnce(JSON.stringify(mockActivePlan))

      await deletePlan('plan-1')

      expect(global.localStorage.setItem).toHaveBeenCalledWith('mockActivePlan', 'null')
    })
  })

  describe('isMock', () => {
    it('should return false when VITE_USE_MOCK is not set', () => {
      expect(isMock()).toBe(false)
    })

    it('should return true when VITE_USE_MOCK is true', () => {
      __setMockEnv({ VITE_USE_MOCK: 'true' })
      expect(isMock()).toBe(true)
    })
  })

  describe('error handling', () => {
    it('should handle network errors', async () => {
      fetch.mockRejectedValueOnce(new Error('Network error'))

      await expect(agentChat({
        message: 'Hello',
        user_id: 'test-user',
        session_id: 'test-session'
      })).rejects.toThrow('Network error')
    })

    it('should handle JSON parse errors', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.reject(new Error('Invalid JSON'))
      })

      await expect(agentChat({
        message: 'Hello',
        user_id: 'test-user',
        session_id: 'test-session'
      })).rejects.toThrow('Invalid JSON')
    })
  })

  describe('helper functions', () => {
    describe('localStorage helpers', () => {
      it('should handle localStorage parsing errors gracefully', async () => {
        global.localStorage.getItem.mockReturnValue('invalid json')
        
        __setMockEnv({ VITE_USE_MOCK: 'true' })
        
        // This should not throw and should return the default value
        const result = await listPlans()
        expect(result.items).toEqual([])
      })

      it('should handle localStorage setItem errors gracefully', async () => {
        global.localStorage.setItem.mockImplementation(() => {
          throw new Error('localStorage full')
        })
        
        __setMockEnv({ VITE_USE_MOCK: 'true' })
        
        // Should not throw
        await expect(createPlan({ title: 'Test' })).resolves.toBeDefined()
      })
    })

    describe('randomId function', () => {
      it('should generate UUID when crypto.randomUUID is available', async () => {
        __setMockEnv({ VITE_USE_MOCK: 'true' })
        
        const result = await createPlan({ title: 'Test' })
        expect(result.id).toBe('mock-uuid-1234')
      })

      it('should fallback to timestamp-based ID when crypto.randomUUID is not available', async () => {
        const originalCrypto = global.crypto
        // Remove crypto temporarily
        delete global.crypto
        
        __setMockEnv({ VITE_USE_MOCK: 'true' })
        
        const result = await createPlan({ title: 'Test' })
        expect(result.id).toMatch(/^\w+-\w+$/) // timestamp.random format
        
        global.crypto = originalCrypto
      })
    })

    describe('mock reply generation', () => {
      it('should generate different replies for different keywords', async () => {
        __setMockEnv({ VITE_USE_MOCK: 'true' })
        
        const onsenResult = await agentChat({ message: '温泉' })
        const kyotoResult = await agentChat({ message: '京都' })
        
        expect(onsenResult.places[0].name).toContain('温泉')
        expect(kyotoResult.places[0].name).toContain('清水寺')
      })

      it('should use default places for generic messages', async () => {
        __setMockEnv({ VITE_USE_MOCK: 'true' })
        
        const result = await agentChat({ message: 'Hello' })
        expect(result.places.length).toBeGreaterThan(0)
        expect(result.places[0].name).toBe('浅草寺')
      })
    })
  })

  describe('API error handling edge cases', () => {
    it('should handle non-OK response without JSON body', async () => {
      fetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.reject(new Error('No JSON'))
      })

      await expect(agentChat({
        message: 'Hello',
        user_id: 'test-user', 
        session_id: 'test-session'
      })).rejects.toThrow('HTTP 500')
    })

    it('should handle timeout and retry logic correctly', async () => {
      jest.useFakeTimers()
      
      // Mock multiple 503 responses
      fetch
        .mockResolvedValueOnce({ ok: false, status: 503 })
        .mockResolvedValueOnce({ ok: false, status: 503 })
        .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ reply: 'success' }) })

      const promise = agentChat({
        message: 'Hello',
        user_id: 'test-user',
        session_id: 'test-session'
      })

      // Fast-forward timers to trigger retries
      await jest.advanceTimersByTimeAsync(5000)
      
      const result = await promise
      expect(result.reply).toBe('success')
      expect(fetch).toHaveBeenCalledTimes(3)
      
      jest.useRealTimers()
    }, 15000)
  })
})