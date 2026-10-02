import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ChatInput from '@/components/ChatInput.vue'

async function typed(text, props = {}) {
  const wrapper = mount(ChatInput, { props })
  await wrapper.get('textarea').setValue(text)
  return wrapper
}

describe('ChatInput', () => {
  it('cannot send while disabled', async () => {
    const wrapper = mount(ChatInput, { props: { disabled: true } })

    await wrapper.get('form').trigger('submit')

    expect(wrapper.get('textarea').attributes('disabled')).toBeDefined()
    expect(wrapper.emitted('send')).toBeUndefined()
  })

  it('does not send blank messages', async () => {
    const wrapper = await typed('   ')

    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('send')).toBeUndefined()
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
  })

  it('sends the trimmed text with Enter and clears the input', async () => {
    const wrapper = await typed('  가격이 얼마예요?  ')

    await wrapper.get('textarea').trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('send')).toEqual([['가격이 얼마예요?']])
    expect(wrapper.get('textarea').element.value).toBe('')
  })

  it('Shift+Enter does not send', async () => {
    const wrapper = await typed('첫 줄')

    await wrapper.get('textarea').trigger('keydown', { key: 'Enter', shiftKey: true })

    expect(wrapper.emitted('send')).toBeUndefined()
  })

  it('ignores Enter while a Korean IME composition is active', async () => {
    const wrapper = await typed('안녕하세')

    await wrapper.get('textarea').trigger('keydown', { key: 'Enter', isComposing: true })
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter', keyCode: 229 })

    expect(wrapper.emitted('send')).toBeUndefined()
  })

  it('blocks sending while a reply is being generated but keeps typing enabled', async () => {
    const wrapper = await typed('다음 질문', { busy: true })

    await wrapper.get('textarea').trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('send')).toBeUndefined()
    expect(wrapper.get('textarea').attributes('disabled')).toBeUndefined()
    expect(wrapper.find('[aria-label="답변 생성 중"]').exists()).toBe(true)
  })

  it('shows the counter and limits input to 1000 characters', async () => {
    const wrapper = await typed('가나다')

    expect(wrapper.get('[data-test="counter"]').text()).toBe('3/1000')
    expect(wrapper.get('textarea').attributes('maxlength')).toBe('1000')
  })
})
