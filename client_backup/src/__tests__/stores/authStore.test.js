/**
 * Comprehensive tests for authStore (Pinia store)
 * Tests authentication state management, JWT handling, and API integration
 */
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '../../stores/authStore'

// Mock fetch globally
global.fetch = jest.fn()

describe('authStore', () => {
  let store

  beforeEach(() => {
    // Create fresh Pinia instance
    setActivePinia(createPinia())
    store = useAuthStore()
    
    // Clear mocks
    jest.clearAllMocks()
    global.localStorage.clear()
    
    // Mock setTimeout for cleanup timer
    jest.useFakeTimers()
  })

  afterEach(() => {
    jest.useRealTimers()
  })

  describe('Initial state', () => {
    it('should have correct initial state', () => {
      expect(store.user).toBeNull()
      expect(store.token).toBeNull()
      expect(store.isAuthenticated).toBe(false)
    })

    it('should load state from localStorage', () => {
      const savedAuth = {
        user: { user_id: 'test', name: 'Test User' },
        token: 'saved-token',
        ts: Date.now()
      }
      global.localStorage.getItem.mockReturnValue(JSON.stringify(savedAuth))
      
      // Create new store to test loading
      const newStore = useAuthStore()
      expect(newStore.user).toEqual(savedAuth.user)
      expect(newStore.token).toBe(savedAuth.token)
    })
  })

  describe('signup', () => {
    it('should successfully sign up user', async () => {
      const mockResponse = {
        user: { user_id: 'newuser', name: 'New User' },
        token: 'new-jwt-token'
      }
      
      fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse)
      })

      await store.signup({
        name: 'New User',
        user_id: 'newuser',
        password: 'password123'
      })

      expect(fetch).toHaveBeenCalledWith('/api/auth/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: 'New User',
          user_id: 'newuser', 
          password: 'password123'
        })
      })

      expect(store.user).toEqual(mockResponse.user)
      expect(store.token).toBe(mockResponse.token)
      expect(store.isAuthenticated).toBe(true)
      expect(global.localStorage.setItem).toHaveBeenCalled()
    })

    it('should validate required fields', async () => {
      // Missing name
      await expect(store.signup({
        user_id: 'test',
        password: 'password123'
      })).rejects.toThrow('必須項目が未入力です')

      // Missing user_id  
      await expect(store.signup({
        name: 'Test',
        password: 'password123'
      })).rejects.toThrow('必須項目が未入力です')

      // Missing password
      await expect(store.signup({
        name: 'Test',
        user_id: 'test'
      })).rejects.toThrow('必須項目が未入力です')
    })

    it('should validate user_id format', async () => {
      await expect(store.signup({
        name: 'Test User',
        user_id: 'invalid user!',  // Invalid characters
        password: 'password123'
      })).rejects.toThrow('ユーザーIDは英小文字・数字・_・-で3〜30文字')
    })

    it('should validate password length', async () => {
      await expect(store.signup({
        name: 'Test User',
        user_id: 'testuser',
        password: '123'  // Too short
      })).rejects.toThrow('パスワードは8文字以上にしてください')
    })

    it('should handle signup API errors', async () => {
      fetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: () => Promise.resolve({ error: 'User already exists' })
      })

      await expect(store.signup({
        name: 'Test User',
        user_id: 'existinguser',
        password: 'password123'
      })).rejects.toThrow('User already exists')
    })
  })

  describe('login', () => {
    it('should successfully log in user', async () => {
      const mockResponse = {
        user: { user_id: 'testuser', name: 'Test User' },
        token: 'login-jwt-token'
      }
      
      fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse)
      })

      await store.login({
        user_id: 'testuser',
        password: 'password123'
      })

      expect(fetch).toHaveBeenCalledWith('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'testuser',
          password: 'password123'
        })
      })

      expect(store.user).toEqual(mockResponse.user)
      expect(store.token).toBe(mockResponse.token)
      expect(store.isAuthenticated).toBe(true)
    })

    it('should validate login fields', async () => {
      // Missing user_id
      await expect(store.login({
        password: 'password123'
      })).rejects.toThrow('ユーザーIDとパスワードを入力してください')

      // Missing password
      await expect(store.login({
        user_id: 'testuser'
      })).rejects.toThrow('ユーザーIDとパスワードを入力してください')
    })

    it('should handle invalid credentials', async () => {
      fetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ error: 'Invalid credentials' })
      })

      await expect(store.login({
        user_id: 'baduser',
        password: 'badpassword'
      })).rejects.toThrow('Invalid credentials')
    })
  })

  describe('JWT token handling', () => {
    it('should check if token is expired', () => {
      // Mock expired token
      const expiredPayload = {
        user_id: 'test',
        exp: Math.floor(Date.now() / 1000) - 3600 // 1 hour ago
      }
      const expiredToken = btoa(JSON.stringify({}) + '.' + JSON.stringify(expiredPayload) + '.signature')
      
      // Set expired token
      store.$state = {
        user: { user_id: 'test' },
        token: expiredToken,
        ts: Date.now()
      }

      expect(store.isTokenExpired()).toBe(true)
      expect(store.isAuthenticated).toBe(false)
    })

    it('should get remaining token time', () => {
      // Mock valid token
      const futureExp = Math.floor(Date.now() / 1000) + 3600 // 1 hour from now
      const validPayload = {
        user_id: 'test',
        exp: futureExp
      }
      const validToken = btoa(JSON.stringify({}) + '.' + JSON.stringify(validPayload) + '.signature')
      
      store.$state = {
        user: { user_id: 'test' },
        token: validToken,
        ts: Date.now()
      }

      const remaining = store.getTokenTimeRemaining()
      expect(remaining).toBeGreaterThan(3500) // Should be close to 3600
      expect(remaining).toBeLessThanOrEqual(3600)
    })

    it('should generate auth headers', () => {
      store.$state = {
        user: { user_id: 'test' },
        token: 'test-token',
        ts: Date.now()
      }

      const headers = store.authHeader()
      expect(headers).toEqual({ Authorization: 'Bearer test-token' })
    })

    it('should return empty headers when no token', () => {
      const headers = store.authHeader()
      expect(headers).toEqual({})
    })
  })

  describe('logout', () => {
    beforeEach(() => {
      // Set up authenticated state
      store.$state = {
        user: { user_id: 'test', name: 'Test User' },
        token: 'test-token',
        ts: Date.now()
      }
    })

    it('should clear authentication state', () => {
      store.logout()

      expect(store.user).toBeNull()
      expect(store.token).toBeNull()
      expect(store.isAuthenticated).toBe(false)
      expect(global.localStorage.removeItem).toHaveBeenCalledWith('travelquiz:auth')
    })

    it('should handle session expiry', () => {
      // Mock window navigation
      const mockDispatchEvent = jest.fn()
      Object.defineProperty(window, 'dispatchEvent', {
        value: mockDispatchEvent,
        writable: true
      })

      store.logout('expired')

      // Should dispatch custom event after timeout
      jest.advanceTimersByTime(100)
      
      expect(mockDispatchEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'auth:expired'
        })
      )
    })
  })

  describe('refreshMe', () => {
    beforeEach(() => {
      store.$state = {
        user: { user_id: 'test' },
        token: 'test-token',
        ts: Date.now()
      }
    })

    it('should refresh user data', async () => {
      const updatedUser = {
        user_id: 'test',
        name: 'Updated User',
        profile: { hobbies: ['travel'] }
      }

      fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(updatedUser)
      })

      const result = await store.refreshMe()

      expect(fetch).toHaveBeenCalledWith('/api/me', {
        headers: { Authorization: 'Bearer test-token' }
      })

      expect(result).toEqual(updatedUser)
      expect(store.user).toEqual(updatedUser)
      expect(global.localStorage.setItem).toHaveBeenCalled()
    })

    it('should handle refresh errors gracefully', async () => {
      fetch.mockResolvedValueOnce({
        ok: false,
        status: 401
      })

      const result = await store.refreshMe()
      expect(result).toBeNull()
    })

    it('should return null when no token', async () => {
      store.$state.token = null
      
      const result = await store.refreshMe()
      expect(result).toBeNull()
      expect(fetch).not.toHaveBeenCalled()
    })
  })

  describe('checkAndCleanExpiredToken', () => {
    it('should clean expired token automatically', () => {
      // Set expired token
      const expiredPayload = {
        user_id: 'test',
        exp: Math.floor(Date.now() / 1000) - 3600
      }
      const expiredToken = btoa(JSON.stringify({}) + '.' + JSON.stringify(expiredPayload) + '.signature')
      
      store.$state = {
        user: { user_id: 'test' },
        token: expiredToken,
        ts: Date.now()
      }

      const wasExpired = store.checkAndCleanExpiredToken()

      expect(wasExpired).toBe(true)
      expect(store.token).toBeNull()
      expect(store.user).toBeNull()
    })

    it('should not clean valid token', () => {
      const validPayload = {
        user_id: 'test',
        exp: Math.floor(Date.now() / 1000) + 3600
      }
      const validToken = btoa(JSON.stringify({}) + '.' + JSON.stringify(validPayload) + '.signature')
      
      store.$state = {
        user: { user_id: 'test' },
        token: validToken,
        ts: Date.now()
      }

      const wasExpired = store.checkAndCleanExpiredToken()

      expect(wasExpired).toBe(false)
      expect(store.token).toBe(validToken)
    })
  })

  describe('API error handling', () => {
    it('should handle network timeouts', async () => {
      jest.useFakeTimers()
      
      // Mock fetch to never resolve (simulate timeout)
      fetch.mockImplementation(() => new Promise(() => {}))

      const signupPromise = store.signup({
        name: 'Test',
        user_id: 'test',
        password: 'password123'
      })

      // Advance timers to trigger timeout
      jest.advanceTimersByTime(15000)

      await expect(signupPromise).rejects.toThrow('タイムアウト')
      
      jest.useRealTimers()
    })

    it('should handle 401 authentication errors', async () => {
      store.$state = {
        user: { user_id: 'test' },
        token: 'test-token',
        ts: Date.now()
      }

      fetch.mockResolvedValueOnce({
        ok: false,
        status: 401
      })

      await expect(store.refreshMe()).resolves.toBeNull()
      
      // Should auto-logout on 401
      expect(store.user).toBeNull()
      expect(store.token).toBeNull()
    })

    it('should handle non-JSON responses', async () => {
      fetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        headers: { get: () => 'text/html' },
        text: () => Promise.resolve('Internal Server Error')
      })

      await expect(store.login({
        user_id: 'test',
        password: 'password'
      })).rejects.toThrow('Internal Server Error')
    })
  })

  describe('localStorage integration', () => {
    it('should handle localStorage errors gracefully', async () => {
      // Mock localStorage.setItem to throw error
      global.localStorage.setItem.mockImplementation(() => {
        throw new Error('localStorage full')
      })

      fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          user: { user_id: 'test' },
          token: 'token'
        })
      })

      // Should not throw even if localStorage fails
      await expect(store.login({
        user_id: 'test',
        password: 'password'
      })).resolves.not.toThrow()

      expect(store.user).toBeDefined()
      expect(store.token).toBeDefined()
    })

    it('should handle corrupt localStorage data', () => {
      global.localStorage.getItem.mockReturnValue('invalid json')
      
      // Should not crash on corrupt data
      expect(() => {
        const newStore = useAuthStore()
      }).not.toThrow()
    })
  })

  describe('concurrent requests', () => {
    it('should handle concurrent login attempts', async () => {
      const mockResponse = {
        user: { user_id: 'test' },
        token: 'token'
      }

      fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResponse)
      })

      // Fire multiple concurrent login requests
      const promises = Array(5).fill().map(() => 
        store.login({ user_id: 'test', password: 'password' })
      )

      const results = await Promise.all(promises)
      
      // All should succeed
      results.forEach(result => {
        expect(result).toBeUndefined() // login returns void on success
      })

      expect(store.user).toEqual(mockResponse.user)
      expect(store.token).toBe(mockResponse.token)
    })
  })
})