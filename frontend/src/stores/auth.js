import { defineStore } from 'pinia'

import * as authApi from '@/api/auth'
import { setAuthToken, setUnauthorizedHandler } from '@/api/client'

export const TOKEN_KEY = 'cs_agent_token'

function readToken() {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

function writeToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    // storage unavailable (private mode): keep the session in memory only
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: null,
    user: null,
    initialized: false,
    initPromise: null,
    loginModalOpen: false,
    redirectPath: null,
  }),

  getters: {
    isAdmin: (state) => state.user?.role === 'ADMIN',
    mustChangePassword: (state) => Boolean(state.user?.must_change_password),
  },

  actions: {
    /**
     * Restore the session from storage once per app start.
     * App.vue and the router guard may both call this; they share one request.
     */
    init() {
      if (this.initialized) return Promise.resolve()
      if (!this.initPromise) {
        setUnauthorizedHandler(() => this.clearSession())
        this.initPromise = this.restoreSession().finally(() => {
          this.initialized = true
        })
      }
      return this.initPromise
    },

    async restoreSession() {
      const token = readToken()
      if (!token) return
      this.setToken(token)
      try {
        const user = await authApi.fetchMe()
        if (this.token === token) this.user = user
      } catch {
        // Only drop the session we were restoring, not one created by a login meanwhile.
        if (this.token === token) this.clearSession()
      }
    },

    setToken(token) {
      this.token = token
      setAuthToken(token)
      writeToken(token)
    },

    clearSession() {
      this.setToken(null)
      this.user = null
    },

    async login(username, password) {
      const { token, user } = await authApi.login(username, password)
      this.setToken(token)
      this.user = user
      // A fresh login is authoritative; never let a pending restore overwrite it.
      this.initialized = true
    },

    async logout() {
      try {
        await authApi.logout()
      } finally {
        this.clearSession()
      }
    },

    async changePassword(currentPassword, newPassword) {
      const { token, user } = await authApi.changePassword(currentPassword, newPassword)
      this.setToken(token)
      this.user = user
    },

    openLoginModal(redirectPath = null) {
      this.redirectPath = redirectPath
      this.loginModalOpen = true
    },

    closeLoginModal() {
      this.loginModalOpen = false
    },

    /** Returns the path to go to after login and forgets it. */
    takeRedirectPath() {
      const path = this.redirectPath
      this.redirectPath = null
      return path
    },
  },
})
