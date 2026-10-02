import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import Pagination from '@/components/Pagination.vue'

describe('Pagination', () => {
  it('is hidden for a single page', () => {
    expect(
      mount(Pagination, { props: { count: 20, page: 1 } })
        .find('nav')
        .exists(),
    ).toBe(false)
  })

  it('shows at most 5 page links around the current page', () => {
    const wrapper = mount(Pagination, { props: { count: 200, page: 6 } })

    const labels = wrapper.findAll('.page-link').map((b) => b.text())
    expect(labels).toEqual(['«', '4', '5', '6', '7', '8', '»'])
    expect(wrapper.get('[aria-current="page"]').text()).toBe('6')
  })

  it('emits page changes and ignores out-of-range clicks', async () => {
    const wrapper = mount(Pagination, { props: { count: 45, page: 1 } })

    await wrapper.get('[aria-label="이전 페이지"]').trigger('click')
    await wrapper.get('[aria-label="다음 페이지"]').trigger('click')

    expect(wrapper.emitted('update:page')).toEqual([[2]])
  })
})
