import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as chatApi from '@/api/chat'
import * as settingsApi from '@/api/settings'
import LlmSettingsCard from '@/components/LlmSettingsCard.vue'

import { apiError } from './helpers'

vi.mock('@/api/settings')
vi.mock('@/api/chat', () => ({ fetchStatus: vi.fn() }))

function provider(name, label, extra = {}) {
  return {
    provider: name,
    label,
    api_key_configured: false,
    api_key_masked: '',
    api_key_updated_at: null,
    model: name === 'anthropic' ? 'claude-opus-5-5' : '',
    default_model: name === 'anthropic' ? 'claude-opus-5-5' : '',
    temperature: null,
    temperature_supported: false, // Opus 5.5 rejects sampling parameters
    temperature_range: name === 'anthropic' ? [0, 1] : [0, 2],
    ...extra,
  }
}

function settings({ active = 'anthropic', claude = {}, openai = {}, gemini = {} } = {}) {
  return {
    llm_provider: active,
    chatbot_enabled: false,
    providers: [
      provider('anthropic', 'Claude', claude),
      provider('openai', 'ChatGPT', openai),
      provider('gemini', 'Gemini', gemini),
    ],
    bot_name: '봇',
    welcome_message: '안녕',
    extra_instructions: '',
  }
}

const CLAUDE_MODELS = {
  models: ['claude-opus-5-5', 'claude-sonnet-5-5', 'claude-haiku-4-5'],
  default_model: 'claude-opus-5-5',
}

async function mountCard(initial = settings()) {
  const wrapper = mount(LlmSettingsCard, {
    props: {
      settings: initial,
      'onUpdate:settings': (value) => wrapper.setProps({ settings: value }),
    },
    attachTo: document.body,
  })
  await flushPromises()
  return wrapper
}

describe('LlmSettingsCard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
    document.body.innerHTML = ''
    chatApi.fetchStatus.mockResolvedValue({ enabled: true, bot_name: 'x', welcome_message: '' })
    settingsApi.listProviderModels.mockResolvedValue(CLAUDE_MODELS)
  })

  it('offers Claude, ChatGPT and Gemini and marks the active one', async () => {
    const wrapper = await mountCard()

    const labels = wrapper.findAll('label.btn').map((l) => l.text())
    expect(labels).toEqual(['Claude', 'ChatGPT', 'Gemini'])
    expect(wrapper.get('#llm-anthropic').element.checked).toBe(true)
    expect(wrapper.get('[data-test="tab-anthropic"]').text()).toContain('사용 중')
  })

  it('shows Claude models with Opus 5.5 as the default even without a key', async () => {
    const wrapper = await mountCard()

    const select = wrapper.get('[data-test="model-select"]')
    expect(select.element.value).toBe('claude-opus-5-5')
    expect(select.text()).toContain('claude-opus-5-5 (기본)')
    expect(select.text()).toContain('claude-sonnet-5-5')
    expect(wrapper.get('[data-test="not-ready"]').text()).toContain('Claude')
  })

  it('changes the Claude model to Sonnet 5.5', async () => {
    settingsApi.updateProviderModel.mockResolvedValue({})
    settingsApi.getSettings.mockResolvedValue(
      settings({ claude: { model: 'claude-sonnet-5-5', api_key_configured: true } }),
    )
    const wrapper = await mountCard(settings({ claude: { api_key_configured: true } }))

    await wrapper.get('[data-test="model-select"]').setValue('claude-sonnet-5-5')
    await flushPromises()

    expect(settingsApi.updateProviderModel).toHaveBeenCalledWith('anthropic', 'claude-sonnet-5-5')
    expect(wrapper.get('[data-test="model-select"]').element.value).toBe('claude-sonnet-5-5')
  })

  it('switches the active provider', async () => {
    settingsApi.updateSettings.mockResolvedValue(settings({ active: 'gemini' }))
    const wrapper = await mountCard()

    await wrapper.get('#llm-gemini').setValue(true)
    await flushPromises()

    expect(settingsApi.updateSettings).toHaveBeenCalledWith({ llm_provider: 'gemini' })
    expect(wrapper.get('[data-test="tab-gemini"]').text()).toContain('사용 중')
    expect(chatApi.fetchStatus).toHaveBeenCalled()
  })

  it('asks for a key before listing ChatGPT models', async () => {
    const wrapper = await mountCard()

    await wrapper.get('[data-test="tab-openai"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="model-select"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('API Key를 등록하면 사용할 수 있는 모델 목록이 표시됩니다.')
  })

  it('saves a provider key, clears the input and lists its models', async () => {
    settingsApi.saveProviderKey.mockResolvedValue(
      settings({ openai: { api_key_configured: true, api_key_masked: 'sk-...ABCD' } }),
    )
    settingsApi.listProviderModels.mockResolvedValue({ models: ['gpt-test-1'], default_model: '' })
    const wrapper = await mountCard()
    await wrapper.get('[data-test="tab-openai"]').trigger('click')

    await wrapper.get('[data-test="key-input"]').setValue('sk-proj-secret-ABCD')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(settingsApi.saveProviderKey).toHaveBeenCalledWith('openai', 'sk-proj-secret-ABCD')
    expect(wrapper.get('[data-test="key-input"]').element.value).toBe('')
    expect(wrapper.get('[data-test="key-masked"]').text()).toBe('sk-...ABCD')
    expect(settingsApi.listProviderModels).toHaveBeenLastCalledWith('openai')
    expect(wrapper.get('[data-test="model-select"]').text()).toContain('모델을 선택하세요')
  })

  it('shows an invalid key error', async () => {
    settingsApi.saveProviderKey.mockRejectedValue(
      apiError(400, { code: 'INVALID_API_KEY', message: '유효하지 않은 API Key입니다.' }),
    )
    const wrapper = await mountCard()

    await wrapper.get('[data-test="key-input"]').setValue('sk-ant-bad-0000')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[data-test="key-error"]').text()).toBe('유효하지 않은 API Key입니다.')
    expect(wrapper.get('[data-test="key-input"]').element.value).toBe('')
  })

  it('deletes a key after confirmation', async () => {
    settingsApi.deleteProviderKey.mockResolvedValue()
    settingsApi.getSettings.mockResolvedValue(settings())
    const wrapper = await mountCard(
      settings({ claude: { api_key_configured: true, api_key_masked: 'sk-ant-...WXYZ' } }),
    )

    await wrapper.get('[data-test="delete-key"]').trigger('click')
    expect(settingsApi.deleteProviderKey).not.toHaveBeenCalled()
    await wrapper.get('[data-test="confirm"]').trigger('click')
    await flushPromises()

    expect(settingsApi.deleteProviderKey).toHaveBeenCalledWith('anthropic')
    expect(wrapper.get('[data-test="key-status"]').text()).toBe('미등록')
  })

  it('shows model listing errors', async () => {
    settingsApi.listProviderModels.mockRejectedValue(
      apiError(502, {
        code: 'LLM_ERROR',
        message: 'LLM API에 연결할 수 없어 확인하지 못했습니다.',
      }),
    )
    const wrapper = await mountCard(settings({ gemini: { api_key_configured: true } }))

    await wrapper.get('[data-test="tab-gemini"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('LLM API에 연결할 수 없어 확인하지 못했습니다.')
  })
})

describe('LlmSettingsCard temperature', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
    document.body.innerHTML = ''
    chatApi.fetchStatus.mockResolvedValue({ enabled: true, bot_name: 'x', welcome_message: '' })
    settingsApi.listProviderModels.mockResolvedValue(CLAUDE_MODELS)
  })

  const fieldset = (wrapper) => wrapper.get('[data-test="temperature"] fieldset')

  it('is disabled with the reason for a model that does not support it (Opus 5.5)', async () => {
    const wrapper = await mountCard()

    expect(fieldset(wrapper).attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-test="temperature-unsupported"]').text()).toContain(
      '선택한 모델(claude-opus-5-5)은 temperature 설정을 지원하지 않습니다.',
    )
  })

  it('is enabled for a supported model and saves the value', async () => {
    const haiku = { model: 'claude-haiku-4-5', temperature_supported: true }
    settingsApi.updateProviderTemperature.mockResolvedValue({})
    settingsApi.getSettings.mockResolvedValue(settings({ claude: { ...haiku, temperature: 0.3 } }))
    const wrapper = await mountCard(settings({ claude: haiku }))

    expect(fieldset(wrapper).attributes('disabled')).toBeUndefined()
    expect(wrapper.find('[data-test="temperature-unsupported"]').exists()).toBe(false)
    expect(wrapper.get('[data-test="temperature-input"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-test="temperature-input"]').attributes('max')).toBe('1')

    await wrapper.get('[data-test="temperature-default"]').setValue(false)
    await wrapper.get('[data-test="temperature-input"]').setValue('0.3')
    await wrapper.get('[data-test="temperature"]').trigger('submit')
    await flushPromises()

    expect(settingsApi.updateProviderTemperature).toHaveBeenCalledWith('anthropic', 0.3)
    expect(wrapper.get('[data-test="temperature-input"]').element.value).toBe('0.3')
  })

  it('saves null when the model default is chosen', async () => {
    const haiku = { model: 'claude-haiku-4-5', temperature_supported: true, temperature: 0.5 }
    settingsApi.updateProviderTemperature.mockResolvedValue({})
    settingsApi.getSettings.mockResolvedValue(settings({ claude: { ...haiku, temperature: null } }))
    const wrapper = await mountCard(settings({ claude: haiku }))
    expect(wrapper.get('[data-test="temperature-default"]').element.checked).toBe(false)

    await wrapper.get('[data-test="temperature-default"]').setValue(true)
    await wrapper.get('[data-test="temperature"]').trigger('submit')
    await flushPromises()

    expect(settingsApi.updateProviderTemperature).toHaveBeenCalledWith('anthropic', null)
  })

  it('shows the server validation message', async () => {
    settingsApi.updateProviderTemperature.mockRejectedValue(
      apiError(400, {
        code: 'VALIDATION_ERROR',
        message: '입력값을 확인해 주세요.',
        details: { temperature: ['0~1 사이의 값을 입력해 주세요.'] },
      }),
    )
    const wrapper = await mountCard(
      settings({ claude: { model: 'claude-haiku-4-5', temperature_supported: true } }),
    )

    await wrapper.get('[data-test="temperature-default"]').setValue(false)
    await wrapper.get('[data-test="temperature-input"]').setValue('1.5')
    await wrapper.get('[data-test="temperature"]').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[data-test="temperature-error"]').text()).toBe(
      '0~1 사이의 값을 입력해 주세요.',
    )
  })

  it('re-evaluates support when the model changes', async () => {
    settingsApi.updateProviderModel.mockResolvedValue({})
    settingsApi.getSettings.mockResolvedValue(
      settings({ claude: { model: 'claude-haiku-4-5', temperature_supported: true } }),
    )
    const wrapper = await mountCard()
    expect(fieldset(wrapper).attributes('disabled')).toBeDefined()

    await wrapper.get('[data-test="model-select"]').setValue('claude-haiku-4-5')
    await flushPromises()

    expect(fieldset(wrapper).attributes('disabled')).toBeUndefined()
  })

  it('asks to choose a model first for ChatGPT without a model', async () => {
    const wrapper = await mountCard(settings({ openai: { api_key_configured: true } }))
    settingsApi.listProviderModels.mockResolvedValue({ models: ['gpt-4.1'], default_model: '' })

    await wrapper.get('[data-test="tab-openai"]').trigger('click')
    await flushPromises()

    expect(fieldset(wrapper).attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-test="temperature-unsupported"]').text()).toBe(
      '모델을 먼저 선택하세요.',
    )
  })
})
