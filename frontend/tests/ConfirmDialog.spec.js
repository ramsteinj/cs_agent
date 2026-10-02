import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ConfirmDialog from '@/components/ConfirmDialog.vue'

describe('ConfirmDialog', () => {
  it('focuses the cancel button when opened and emits on Esc', async () => {
    const wrapper = mount(ConfirmDialog, {
      props: { show: false, message: '삭제할까요?' },
      attachTo: document.body,
    })

    await wrapper.setProps({ show: true })
    await flushPromises()

    expect(document.activeElement?.textContent.trim()).toBe('취소')
    await wrapper.get('[role="dialog"]').trigger('keydown', { key: 'Escape' })
    expect(wrapper.emitted('cancel')).toHaveLength(1)
    wrapper.unmount()
  })

  it('emits confirm', async () => {
    const wrapper = mount(ConfirmDialog, { props: { show: true, message: 'x' } })

    await wrapper.get('[data-test="confirm"]').trigger('click')

    expect(wrapper.emitted('confirm')).toHaveLength(1)
  })
})
