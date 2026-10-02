import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '@/api/auth'
import { createAppRouter } from '@/router'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/api/auth', () => ({
  login: vi.fn(),
  logout: vi.fn(),
  fetchMe: vi.fn(),
  changePassword: vi.fn(),
}))

describe('admin route guard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('redirects anonymous users home and opens the login modal', async () => {
    const router = createAppRouter(createMemoryHistory())

    await router.push('/admin/settings')

    const auth = useAuthStore()
    expect(router.currentRoute.value.path).toBe('/')
    expect(auth.loginModalOpen).toBe(true)
    expect(auth.redirectPath).toBe('/admin/settings')
  })

  it('lets admins through', async () => {
    authApi.login.mockResolvedValueOnce({
      token: 't',
      user: { id: 1, username: 'admin', role: 'ADMIN', must_change_password: false },
    })
    const auth = useAuthStore()
    await auth.init()
    await auth.login('admin', 'admin1234!')
    const router = createAppRouter(createMemoryHistory())

    await router.push('/admin')

    expect(router.currentRoute.value.path).toBe('/admin/settings')
  })

  it('does not guard the public chat page', async () => {
    const router = createAppRouter(createMemoryHistory())

    await router.push('/')

    expect(router.currentRoute.value.path).toBe('/')
    expect(useAuthStore().loginModalOpen).toBe(false)
  })
})
