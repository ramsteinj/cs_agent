import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as knowledgeApi from '@/api/knowledge'
import CompanyListView from '@/views/admin/CompanyListView.vue'

import { mountRoute } from './helpers'

vi.mock('@/api/knowledge')

const ROWS = [
  { id: 1, name: '알파', phone: '02-1', email: '', product_count: 2, chunk_count: 1 },
  { id: 2, name: '베타', phone: '', email: 'b@x.com', product_count: 0, chunk_count: 1 },
]

describe('CompanyListView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    document.body.innerHTML = ''
    knowledgeApi.listCompanies.mockResolvedValue({ count: 2, results: ROWS })
  })

  it('lists companies', async () => {
    const { wrapper } = await mountRoute(CompanyListView, { path: '/admin/companies' })

    expect(wrapper.findAll('[data-test="company-row"]')).toHaveLength(2)
    expect(knowledgeApi.listCompanies).toHaveBeenCalledWith({ page: 1 })
  })

  it('searches by name from page 1', async () => {
    const { wrapper } = await mountRoute(CompanyListView, { path: '/admin/companies' })

    await wrapper.get('#company-search').setValue(' 알 ')
    await wrapper.get('form[role="search"]').trigger('submit')

    expect(knowledgeApi.listCompanies).toHaveBeenLastCalledWith({ page: 1, search: '알' })
  })

  it('shows the empty state', async () => {
    knowledgeApi.listCompanies.mockResolvedValue({ count: 0, results: [] })
    const { wrapper } = await mountRoute(CompanyListView, { path: '/admin/companies' })

    expect(wrapper.get('[data-test="empty"]').text()).toBe('등록된 회사가 없습니다.')
  })

  it('warns about cascading product deletion and deletes after confirm', async () => {
    knowledgeApi.deleteCompany.mockResolvedValue()
    const { wrapper } = await mountRoute(CompanyListView, { path: '/admin/companies' })

    await wrapper.findAll('[data-test="delete"]')[0].trigger('click')
    expect(document.body.textContent).toContain('소속 제품 2개도 함께 삭제됩니다.')
    expect(knowledgeApi.deleteCompany).not.toHaveBeenCalled()

    await wrapper.get('[data-test="confirm"]').trigger('click')
    await flushPromises()

    expect(knowledgeApi.deleteCompany).toHaveBeenCalledWith(1)
    expect(knowledgeApi.listCompanies).toHaveBeenCalledTimes(2) // reloaded
  })
})
