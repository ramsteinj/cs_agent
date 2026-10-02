import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '@/api/auth'
import SettingsView from '@/views/admin/SettingsView.vue'

vi.mock('@/api/auth', () => ({
  login: vi.fn(),
  logout: vi.fn(),
  fetchMe: vi.fn(),
  changePassword: vi.fn(),
}))

async function fill(wrapper, current, next, confirm) {
  await wrapper.get('#pw-current').setValue(current)
  await wrapper.get('#pw-new').setValue(next)
  await wrapper.get('#pw-confirm').setValue(confirm)
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

describe('SettingsView password card', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('rejects a mismatched confirmation without calling the API', async () => {
    const wrapper = mount(SettingsView)

    await fill(wrapper, 'old-pass', 'N3w-Secure-pass', 'different')

    expect(authApi.changePassword).not.toHaveBeenCalled()
    expect(wrapper.get('#pw-confirm').classes()).toContain('is-invalid')
  })

  it('shows field errors returned by the server', async () => {
    authApi.changePassword.mockRejectedValueOnce({
      response: {
        status: 400,
        data: {
          error: {
            code: 'VALIDATION_ERROR',
            message: '입력값을 확인해 주세요.',
            details: { current_password: ['현재 비밀번호가 올바르지 않습니다.'] },
          },
        },
      },
    })
    const wrapper = mount(SettingsView)

    await fill(wrapper, 'wrong', 'N3w-Secure-pass', 'N3w-Secure-pass')

    expect(wrapper.get('#pw-current').classes()).toContain('is-invalid')
    expect(wrapper.text()).toContain('현재 비밀번호가 올바르지 않습니다.')
  })

  it('clears the form on success', async () => {
    authApi.changePassword.mockResolvedValueOnce({
      token: 't2',
      user: { id: 1, username: 'admin', role: 'ADMIN', must_change_password: false },
    })
    const wrapper = mount(SettingsView)

    await fill(wrapper, 'admin1234!', 'N3w-Secure-pass', 'N3w-Secure-pass')

    expect(authApi.changePassword).toHaveBeenCalledWith('admin1234!', 'N3w-Secure-pass')
    expect(wrapper.get('#pw-current').element.value).toBe('')
  })
})
