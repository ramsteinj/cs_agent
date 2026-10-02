import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '@/api/auth'
import { TOKEN_KEY, useAuthStore } from '@/stores/auth'

vi.mock('@/api/auth', () => ({
  login: vi.fn(),
  logout: vi.fn(),
  fetchMe: vi.fn(),
  changePassword: vi.fn(),
}))

const ADMIN = { id: 1, username: 'admin', role: 'ADMIN', must_change_password: true }

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('login stores the token and user', async () => {
    authApi.login.mockResolvedValueOnce({ token: 'tok-1', user: ADMIN })
    const auth = useAuthStore()

    await auth.login('admin', 'admin1234!')

    expect(localStorage.getItem(TOKEN_KEY)).toBe('tok-1')
    expect(auth.isAdmin).toBe(true)
    expect(auth.mustChangePassword).toBe(true)
  })

  it('logout clears the session even if the API call fails', async () => {
    authApi.login.mockResolvedValueOnce({ token: 'tok-1', user: ADMIN })
    authApi.logout.mockRejectedValueOnce(new Error('network'))
    const auth = useAuthStore()
    await auth.login('admin', 'admin1234!')

    await expect(auth.logout()).rejects.toThrow()

    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
    expect(auth.isAdmin).toBe(false)
  })

  it('init restores a valid stored session', async () => {
    localStorage.setItem(TOKEN_KEY, 'tok-saved')
    authApi.fetchMe.mockResolvedValueOnce(ADMIN)
    const auth = useAuthStore()

    await auth.init()

    expect(auth.token).toBe('tok-saved')
    expect(auth.user).toEqual(ADMIN)
  })

  it('init drops an invalid stored token', async () => {
    localStorage.setItem(TOKEN_KEY, 'tok-expired')
    authApi.fetchMe.mockRejectedValueOnce({ response: { status: 401 } })
    const auth = useAuthStore()

    await auth.init()

    expect(auth.token).toBeNull()
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
  })

  it('changePassword replaces token and clears the flag', async () => {
    authApi.login.mockResolvedValueOnce({ token: 'tok-1', user: ADMIN })
    authApi.changePassword.mockResolvedValueOnce({
      token: 'tok-2',
      user: { ...ADMIN, must_change_password: false },
    })
    const auth = useAuthStore()
    await auth.login('admin', 'admin1234!')

    await auth.changePassword('admin1234!', 'N3w-Secure-pass')

    expect(localStorage.getItem(TOKEN_KEY)).toBe('tok-2')
    expect(auth.mustChangePassword).toBe(false)
  })

  it('takeRedirectPath returns the path once', () => {
    const auth = useAuthStore()
    auth.openLoginModal('/admin/settings')

    expect(auth.loginModalOpen).toBe(true)
    expect(auth.takeRedirectPath()).toBe('/admin/settings')
    expect(auth.takeRedirectPath()).toBeNull()
  })
})

describe('auth store init races', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('concurrent init calls share one /auth/me request', async () => {
    localStorage.setItem(TOKEN_KEY, 'tok-saved')
    authApi.fetchMe.mockResolvedValue(ADMIN)
    const auth = useAuthStore()

    await Promise.all([auth.init(), auth.init()])

    expect(authApi.fetchMe).toHaveBeenCalledTimes(1)
  })

  it('a failing restore does not wipe a login that happened meanwhile', async () => {
    localStorage.setItem(TOKEN_KEY, 'tok-expired')
    let rejectMe
    authApi.fetchMe.mockReturnValueOnce(new Promise((_, reject) => (rejectMe = reject)))
    authApi.login.mockResolvedValueOnce({ token: 'tok-new', user: ADMIN })
    const auth = useAuthStore()

    const pending = auth.init()
    await auth.login('admin', 'admin1234!')
    rejectMe({ response: { status: 401 } })
    await pending

    expect(auth.token).toBe('tok-new')
    expect(auth.isAdmin).toBe(true)
  })
})
