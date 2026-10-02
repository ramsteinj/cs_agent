import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ChatMessage from '@/components/ChatMessage.vue'

const base = { key: 1, role: 'assistant', content: '', sources: [], status: 'ok', errorText: '' }

describe('ChatMessage', () => {
  it('renders bot answers as sanitized Markdown', () => {
    const wrapper = mount(ChatMessage, {
      props: { message: { ...base, content: '**14일 무료 체험**<img src=x onerror=alert(1)>' } },
    })

    expect(wrapper.get('[data-test="markdown"] strong').text()).toBe('14일 무료 체험')
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.html()).not.toContain('onerror')
  })

  it('keeps the customer message as plain text', () => {
    const wrapper = mount(ChatMessage, {
      props: { message: { ...base, role: 'user', content: '**굵게** <img src=x>' } },
    })

    expect(wrapper.find('strong').exists()).toBe(false)
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toBe('**굵게** <img src=x>')
  })

  it('shows a typing indicator while waiting for the first delta', () => {
    const wrapper = mount(ChatMessage, { props: { message: { ...base, status: 'streaming' } } })

    expect(wrapper.find('[data-test="typing"]').exists()).toBe(true)
  })

  it('lists sources under a completed answer', () => {
    const wrapper = mount(ChatMessage, {
      props: { message: { ...base, content: '답', sources: [{ title: 'A' }, { title: 'B' }] } },
    })

    expect(wrapper.get('[data-test="sources"]').text()).toBe('참고: A, B')
  })

  it('shows the error with a retry button', async () => {
    const message = { ...base, status: 'error', errorText: '일시적인 오류' }
    const wrapper = mount(ChatMessage, { props: { message } })

    await wrapper.get('[data-test="retry"]').trigger('click')

    expect(wrapper.get('[data-test="message-error"]').text()).toContain('일시적인 오류')
    expect(wrapper.emitted('retry')).toEqual([[message]])
  })
})
