import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '@/api/auth'
import * as chatApi from '@/api/chat'
import * as knowledgeApi from '@/api/knowledge'
import * as settingsApi from '@/api/settings'
import SettingsView from '@/views/admin/SettingsView.vue'

vi.mock('@/api/auth', () => ({
  login: vi.fn(),
  logout: vi.fn(),
  fetchMe: vi.fn(),
  changePassword: vi.fn(),
}))
vi.mock('@/api/settings', () => ({
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
  saveProviderKey: vi.fn(),
  deleteProviderKey: vi.fn(),
  updateProviderModel: vi.fn(),
  listProviderModels: vi.fn(),
  getRagSettings: vi.fn(),
  updateRagSettings: vi.fn(),
}))
vi.mock('@/api/chat', () => ({ fetchStatus: vi.fn() }))
vi.mock('@/api/knowledge', () => ({ getStats: vi.fn(), reindex: vi.fn() }))

const PROVIDERS = [
  {
    provider: 'anthropic',
    label: 'Claude',
    api_key_configured: false,
    api_key_masked: '',
    api_key_updated_at: null,
    model: 'claude-opus-5-5',
    default_model: 'claude-opus-5-5',
  },
  {
    provider: 'openai',
    label: 'ChatGPT',
    api_key_configured: false,
    api_key_masked: '',
    api_key_updated_at: null,
    model: '',
    default_model: '',
  },
  {
    provider: 'gemini',
    label: 'Gemini',
    api_key_configured: false,
    api_key_masked: '',
    api_key_updated_at: null,
    model: '',
    default_model: '',
  },
]
const BASE = {
  llm_provider: 'anthropic',
  chatbot_enabled: false,
  providers: PROVIDERS,
  bot_name: '고객지원 챗봇',
  welcome_message: '안녕하세요!',
  system_prompt: '당신은 "{bot_name}"입니다. (수정됨)',
  default_system_prompt: '당신은 "{bot_name}"입니다. (기본)',
  extra_instructions: '',
}

const STATS = {
  companies: 1,
  products: 3,
  chunks: 4,
  embedding_model: 'intfloat/multilingual-e5-small',
  embedding_dim: 384,
}

function apiError(status, error) {
  return { response: { status, data: { error } } }
}

async function mountView(initial = BASE) {
  settingsApi.getSettings.mockResolvedValueOnce(initial)
  const wrapper = mount(SettingsView, { attachTo: document.body })
  await flushPromises()
  return wrapper
}

describe('SettingsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks() // also drops queued *Once values left by a previous test
    settingsApi.getRagSettings.mockReturnValue(new Promise(() => {})) // own spec
    settingsApi.listProviderModels.mockResolvedValue({ models: [], default_model: '' })
    chatApi.fetchStatus.mockResolvedValue({ enabled: true, bot_name: 'x', welcome_message: 'y' })
    knowledgeApi.getStats.mockResolvedValue(STATS)
    document.body.innerHTML = ''
  })

  it('shows the LLM card for the loaded settings', async () => {
    const wrapper = await mountView()

    expect(wrapper.find('[data-test="llm-card"]').exists()).toBe(true)
  })

  describe('chatbot settings card', () => {
    it('saves the form and shows field errors', async () => {
      settingsApi.updateSettings.mockRejectedValueOnce(
        apiError(400, {
          code: 'VALIDATION_ERROR',
          message: '입력값을 확인해 주세요.',
          details: { extra_instructions: ['2000자 이하로 입력해 주세요.'] },
        }),
      )
      const wrapper = await mountView()

      await wrapper.get('#bot-extra').setValue('친근하게')
      await wrapper.get('[data-test="bot-card"] form').trigger('submit')
      await flushPromises()

      expect(settingsApi.updateSettings).toHaveBeenCalledWith({
        bot_name: '고객지원 챗봇',
        welcome_message: '안녕하세요!',
        system_prompt: '당신은 "{bot_name}"입니다. (수정됨)',
        extra_instructions: '친근하게',
      })
      expect(wrapper.get('#bot-extra').classes()).toContain('is-invalid')
    })

    it('shows the extra instructions counter', async () => {
      const wrapper = await mountView()

      await wrapper.get('#bot-extra').setValue('가나다')

      expect(wrapper.get('[data-test="extra-counter"]').text()).toBe('3/2000')
    })
  })

  describe('system prompt', () => {
    it('shows the stored prompt and resets it to the default', async () => {
      settingsApi.updateSettings.mockResolvedValueOnce({
        ...BASE,
        system_prompt: BASE.default_system_prompt,
      })
      const wrapper = await mountView()
      const textarea = wrapper.get('#bot-prompt')
      expect(textarea.element.value).toBe(BASE.system_prompt)

      await wrapper.get('[data-test="reset-prompt"]').trigger('click')
      expect(textarea.element.value).toBe(BASE.default_system_prompt)
      expect(settingsApi.updateSettings).not.toHaveBeenCalled() // only on save

      await wrapper.get('[data-test="bot-card"] form').trigger('submit')
      await flushPromises()

      expect(settingsApi.updateSettings).toHaveBeenCalledWith(
        expect.objectContaining({ system_prompt: BASE.default_system_prompt }),
      )
      expect(wrapper.get('[data-test="reset-prompt"]').attributes('disabled')).toBeDefined()
    })

    it('shows the counter and blocks saving an empty prompt', async () => {
      const wrapper = await mountView()

      await wrapper.get('#bot-prompt').setValue('   ')

      expect(wrapper.get('[data-test="prompt-counter"]').text()).toBe('3/10000')
      expect(wrapper.get('[data-test="save-bot"]').attributes('disabled')).toBeDefined()
    })

    it('shows the server validation message', async () => {
      settingsApi.updateSettings.mockRejectedValueOnce(
        apiError(400, {
          code: 'VALIDATION_ERROR',
          message: '입력값을 확인해 주세요.',
          details: { system_prompt: ['시스템 프롬프트를 입력해 주세요.'] },
        }),
      )
      const wrapper = await mountView()

      await wrapper.get('[data-test="bot-card"] form').trigger('submit')
      await flushPromises()

      expect(wrapper.get('#bot-prompt').classes()).toContain('is-invalid')
    })
  })

  describe('knowledge index card', () => {
    it('shows stats', async () => {
      const wrapper = await mountView()

      const text = wrapper.get('[data-test="index-stats"]').text()
      expect(text).toContain('1 / 3')
      expect(text).toContain('intfloat/multilingual-e5-small (384차원)')
    })

    it('reindexes after confirmation and refreshes stats', async () => {
      knowledgeApi.reindex.mockResolvedValueOnce({ chunks: 4 })
      const wrapper = await mountView()

      await wrapper.get('[data-test="reindex"]').trigger('click')
      expect(knowledgeApi.reindex).not.toHaveBeenCalled()
      await wrapper.get('[data-test="confirm"]').trigger('click')
      await flushPromises()

      expect(knowledgeApi.reindex).toHaveBeenCalledTimes(1)
      expect(knowledgeApi.getStats).toHaveBeenCalledTimes(2)
    })
  })

  describe('password card', () => {
    async function fill(wrapper, current, next, confirm) {
      await wrapper.get('#pw-current').setValue(current)
      await wrapper.get('#pw-new').setValue(next)
      await wrapper.get('#pw-confirm').setValue(confirm)
      await wrapper.get('[data-test="password-card"] form').trigger('submit')
      await flushPromises()
    }

    it('rejects a mismatched confirmation without calling the API', async () => {
      const wrapper = await mountView()

      await fill(wrapper, 'old-pass', 'N3w-Secure-pass', 'different')

      expect(authApi.changePassword).not.toHaveBeenCalled()
      expect(wrapper.get('#pw-confirm').classes()).toContain('is-invalid')
    })

    it('shows field errors returned by the server', async () => {
      authApi.changePassword.mockRejectedValueOnce(
        apiError(400, {
          code: 'VALIDATION_ERROR',
          message: '입력값을 확인해 주세요.',
          details: { current_password: ['현재 비밀번호가 올바르지 않습니다.'] },
        }),
      )
      const wrapper = await mountView()

      await fill(wrapper, 'wrong', 'N3w-Secure-pass', 'N3w-Secure-pass')

      expect(wrapper.get('#pw-current').classes()).toContain('is-invalid')
      expect(wrapper.text()).toContain('현재 비밀번호가 올바르지 않습니다.')
    })

    it('clears the form on success', async () => {
      authApi.changePassword.mockResolvedValueOnce({
        token: 't2',
        user: { id: 1, username: 'admin', role: 'ADMIN', must_change_password: false },
      })
      const wrapper = await mountView()

      await fill(wrapper, 'admin1234!', 'N3w-Secure-pass', 'N3w-Secure-pass')

      expect(authApi.changePassword).toHaveBeenCalledWith('admin1234!', 'N3w-Secure-pass')
      expect(wrapper.get('#pw-current').element.value).toBe('')
    })

    it('is still usable when settings fail to load', async () => {
      settingsApi.getSettings.mockRejectedValueOnce(
        apiError(500, { code: 'ERROR', message: '요청을 처리할 수 없습니다.' }),
      )
      const wrapper = mount(SettingsView)
      await flushPromises()

      expect(wrapper.text()).toContain('요청을 처리할 수 없습니다.')
      expect(wrapper.find('[data-test="password-card"]').exists()).toBe(true)
    })
  })
})
