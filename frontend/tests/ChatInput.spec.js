import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ChatInput from '@/components/ChatInput.vue'

describe('ChatInput', () => {
  it('cannot send while disabled', async () => {
    const wrapper = mount(ChatInput, { props: { disabled: true } })

    await wrapper.get('form').trigger('submit')

    expect(wrapper.get('textarea').attributes('disabled')).toBeDefined()
    expect(wrapper.emitted('send')).toBeUndefined()
  })

  it('does not send blank messages', async () => {
    const wrapper = mount(ChatInput)
    await wrapper.get('textarea').setValue('   ')

    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('send')).toBeUndefined()
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
  })

  it('emits the trimmed text and clears the input', async () => {
    const wrapper = mount(ChatInput)
    await wrapper.get('textarea').setValue('  가격이 얼마예요?  ')

    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('send')).toEqual([['가격이 얼마예요?']])
    expect(wrapper.get('textarea').element.value).toBe('')
  })

  it('limits input length to 1000 characters', () => {
    const wrapper = mount(ChatInput)

    expect(wrapper.get('textarea').attributes('maxlength')).toBe('1000')
  })
})
