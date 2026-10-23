import { defineStore } from 'pinia'

const TOKEN_KEY = 'english_practice_token'
const USER_KEY = 'english_practice_user'

function readStoredUser() {
  try {
    return JSON.parse(window.localStorage.getItem(USER_KEY) || 'null')
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: window.localStorage.getItem(TOKEN_KEY) || '',
    user: readStoredUser(),
    initialized: false,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token),
    isAdmin: (state) => state.user?.role === 'admin',
  },
  actions: {
    setToken(token) {
      this.token = token || ''
      if (this.token) {
        window.localStorage.setItem(TOKEN_KEY, this.token)
      } else {
        window.localStorage.removeItem(TOKEN_KEY)
      }
    },
    setSession(session) {
      this.setToken(session.access_token)
      this.user = session.user
      window.localStorage.setItem(USER_KEY, JSON.stringify(session.user))
      this.initialized = true
    },
    clearSession() {
      this.token = ''
      this.user = null
      window.localStorage.removeItem(TOKEN_KEY)
      window.localStorage.removeItem(USER_KEY)
      this.initialized = true
    },
    logout() {
      this.clearSession()
    },
    async login(credentials) {
      const authApi = await import('../api/auth')
      const session = await authApi.login(credentials)
      this.setSession(session)
      return session.user
    },
    async fetchMe() {
      if (!this.token) {
        this.initialized = true
        return null
      }
      try {
        const authApi = await import('../api/auth')
        this.user = await authApi.fetchMe()
        window.localStorage.setItem(USER_KEY, JSON.stringify(this.user))
        return this.user
      } catch (error) {
        this.clearSession()
        throw error
      } finally {
        this.initialized = true
      }
    },
  },
})
