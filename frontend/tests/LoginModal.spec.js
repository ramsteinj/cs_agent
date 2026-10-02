import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '@/api/auth'
import LoginModal from '@/components/LoginModal.vue'
import { createAppRouter } from '@/router'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/api/auth', () => ({
  login: vi.fn(),
  logout: vi.fn(),
  fetchMe: vi.fn(),
  changePassword: vi.fn(),
}))

const ADMIN = { id: 1, username: 'admin', role: 'ADMIN', must_change_password: false }

async function mountOpen(redirect = null) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createAppRouter(createMemoryHistory())
  await router.push('/')
  const auth = useAuthStore()
  const wrapper = mount(LoginModal, { global: { plugins: [pinia, router] } })
  auth.openLoginModal(redirect)
  await flushPromises()
  return { wrapper, auth, router }
}

async function submit(wrapper, username, password) {
  await wrapper.get('#login-username').setValue(username)
  await wrapper.get('#login-password').setValue(password)
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

describe('LoginModal', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('is hidden until opened', () => {
    setActivePinia(createPinia())
    const wrapper = mount(LoginModal, {
      global: { plugins: [createAppRouter(createMemoryHistory())] },
    })
    expect(wrapper.find('form').exists()).toBe(false)
  })

  it('shows the server message on failure and stays open', async () => {
    authApi.login.mockRejectedValueOnce({
      response: {
        status: 401,
        data: {
          error: {
            code: 'INVALID_CREDENTIALS',
            message: '아이디 또는 비밀번호가 올바르지 않습니다.',
          },
        },
      },
    })
    const { wrapper, auth } = await mountOpen()

    await submit(wrapper, 'admin', 'wrong')

    expect(wrapper.get('[data-test="login-error"]').text()).toBe(
      '아이디 또는 비밀번호가 올바르지 않습니다.',
    )
    expect(auth.loginModalOpen).toBe(true)
  })

  it('closes and navigates to the redirect path on success', async () => {
    authApi.login.mockResolvedValueOnce({ token: 't', user: ADMIN })
    const { wrapper, auth, router } = await mountOpen('/admin/settings')

    await submit(wrapper, 'admin', 'admin1234!')

    expect(auth.loginModalOpen).toBe(false)
    // admin views are lazy-loaded, so navigation settles asynchronously
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/admin/settings'))
  })
})
