import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useChatStore } from '@/stores/chat'
import ChatView from '@/views/ChatView.vue'

function mountWith(state) {
  const pinia = createPinia()
  setActivePinia(pinia)
  Object.assign(useChatStore(), { statusLoaded: true, ...state })
  return mount(ChatView, { global: { plugins: [pinia] } })
}

describe('ChatView', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('disables input and shows the notice when no API Key is set (F-U2)', () => {
    const wrapper = mountWith({ enabled: false })

    const textarea = wrapper.get('textarea')
    expect(textarea.attributes('disabled')).toBeDefined()
    expect(textarea.attributes('placeholder')).toBe('현재 상담 서비스를 준비 중입니다.')
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-test="chat-notice"]').text()).toBe(
      '현재 상담 서비스를 준비 중입니다.',
    )
  })

  it('shows the welcome message and enables input when enabled', () => {
    const wrapper = mountWith({ enabled: true, welcomeMessage: '무엇을 도와드릴까요?' })

    expect(wrapper.get('textarea').attributes('disabled')).toBeUndefined()
    expect(wrapper.get('[data-test="welcome"]').text()).toBe('무엇을 도와드릴까요?')
    expect(wrapper.find('[data-test="chat-notice"]').exists()).toBe(false)
  })

  it('keeps input disabled while the status is loading', () => {
    const wrapper = mountWith({ statusLoaded: false, enabled: false })

    expect(wrapper.get('textarea').attributes('disabled')).toBeDefined()
    expect(wrapper.find('[data-test="chat-loading"]').exists()).toBe(true)
  })

  it('shows an error and stays disabled when the status request failed', () => {
    const wrapper = mountWith({ enabled: false, statusError: true })

    expect(wrapper.get('textarea').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-test="chat-notice"]').text()).toContain('일시적인 오류')
  })
})
