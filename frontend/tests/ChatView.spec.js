import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useChatStore } from '@/stores/chat'
import ChatView from '@/views/ChatView.vue'

vi.mock('@/api/chat', () => ({
  ChatRequestError: class extends Error {},
  fetchStatus: vi.fn(),
  createSession: vi.fn(),
  fetchMessages: vi.fn(),
  streamMessage: vi.fn(),
}))

function mountWith(state) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const chat = useChatStore()
  Object.assign(chat, { statusLoaded: true, ...state })
  return { wrapper: mount(ChatView, { global: { plugins: [pinia] } }), chat }
}

describe('ChatView', () => {
  beforeEach(() => sessionStorage.clear())

  it('disables input and shows the notice when no API Key is set (F-U2)', () => {
    const { wrapper } = mountWith({ enabled: false })

    const textarea = wrapper.get('textarea')
    expect(textarea.attributes('disabled')).toBeDefined()
    expect(textarea.attributes('placeholder')).toBe('현재 상담 서비스를 준비 중입니다.')
    expect(wrapper.get('[data-test="chat-notice"]').text()).toBe(
      '현재 상담 서비스를 준비 중입니다.',
    )
  })

  it('shows the welcome message and conversation when enabled', () => {
    const { wrapper } = mountWith({
      enabled: true,
      welcomeMessage: '무엇을 도와드릴까요?',
      messages: [
        { key: 1, role: 'user', content: '질문', sources: [], status: 'ok' },
        { key: 2, role: 'assistant', content: '답변', sources: [], status: 'ok' },
      ],
    })

    expect(wrapper.get('[data-test="welcome"]').text()).toBe('무엇을 도와드릴까요?')
    expect(wrapper.get('[data-test="message-user"]').text()).toBe('질문')
    expect(wrapper.get('[data-test="message-assistant"]').text()).toContain('답변')
    expect(wrapper.get('textarea').attributes('disabled')).toBeUndefined()
  })

  it('keeps input disabled while the status is loading', () => {
    const { wrapper } = mountWith({ statusLoaded: false, enabled: false })

    expect(wrapper.get('textarea').attributes('disabled')).toBeDefined()
    expect(wrapper.find('[data-test="chat-loading"]').exists()).toBe(true)
  })

  it('shows an error and stays disabled when the status request failed', () => {
    const { wrapper } = mountWith({ enabled: false, statusError: true })

    expect(wrapper.get('textarea').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-test="chat-notice"]').text()).toContain('일시적인 오류')
  })

  it('sends input through the store and resets with "새 대화"', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const chat = useChatStore()
    Object.assign(chat, {
      statusLoaded: true,
      enabled: true,
      messages: [{ key: 1, role: 'user', content: 'x', sources: [], status: 'ok' }],
    })
    // Spy before mounting: the template binds the handlers at render time.
    const send = vi.spyOn(chat, 'send').mockResolvedValue()
    const reset = vi.spyOn(chat, 'reset')
    const wrapper = mount(ChatView, { global: { plugins: [pinia] } })

    await wrapper.get('textarea').setValue('새 질문')
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter' })
    await wrapper.get('[data-test="new-chat"]').trigger('click')

    expect(send).toHaveBeenCalledWith('새 질문')
    expect(reset).toHaveBeenCalled()
  })

  it('disables "새 대화" while an answer is streaming', () => {
    const { wrapper } = mountWith({
      enabled: true,
      streaming: true,
      messages: [{ key: 1, role: 'user', content: 'x', sources: [], status: 'ok' }],
    })

    expect(wrapper.get('[data-test="new-chat"]').attributes('disabled')).toBeDefined()
  })
})
