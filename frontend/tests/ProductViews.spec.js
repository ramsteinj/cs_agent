import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as knowledgeApi from '@/api/knowledge'
import ProductFormView from '@/views/admin/ProductFormView.vue'
import ProductListView from '@/views/admin/ProductListView.vue'

import { mountRoute } from './helpers'

vi.mock('@/api/knowledge')

const COMPANIES = [
  { id: 1, name: '알파' },
  { id: 2, name: '베타' },
]

describe('ProductListView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    document.body.innerHTML = ''
    knowledgeApi.listProducts.mockResolvedValue({
      count: 1,
      results: [
        {
          id: 5,
          name: '드라이브',
          company_name: '알파',
          category: '문서',
          price: '월 5,000원',
          is_active: false,
          chunk_count: 2,
        },
      ],
    })
    knowledgeApi.listAllCompanies.mockResolvedValue(COMPANIES)
    knowledgeApi.listCategories.mockResolvedValue(['문서', '일정'])
  })

  it('renders rows with the active badge', async () => {
    const { wrapper } = await mountRoute(ProductListView, { path: '/admin/products' })

    const row = wrapper.get('[data-test="product-row"]')
    expect(row.text()).toContain('드라이브')
    expect(row.text()).toContain('비활성')
  })

  it('sends selected filters to the API', async () => {
    const { wrapper } = await mountRoute(ProductListView, { path: '/admin/products' })

    await wrapper.get('#filter-company').setValue('2')
    await wrapper.get('#filter-category').setValue('일정')
    await wrapper.get('#filter-active').setValue('false')
    await flushPromises()

    expect(knowledgeApi.listProducts).toHaveBeenLastCalledWith({
      page: 1,
      company: '2',
      category: '일정',
      is_active: 'false',
    })
  })
})

describe('ProductFormView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    document.body.innerHTML = ''
    knowledgeApi.listAllCompanies.mockResolvedValue(COMPANIES)
    knowledgeApi.listCategories.mockResolvedValue(['문서'])
  })

  it('preselects the company from the query and creates the product', async () => {
    knowledgeApi.createProduct.mockResolvedValue({ id: 9 })
    const { wrapper, router } = await mountRoute(ProductFormView, {
      path: '/admin/products/new?company=2',
      pattern: '/admin/products/new',
    })

    expect(wrapper.get('#product-company').element.value).toBe('2')
    await wrapper.get('#product-name').setValue('캘린더')
    await wrapper.get('#product-description').setValue('일정 관리')
    await wrapper.get('#product-active').setValue(false)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(knowledgeApi.createProduct).toHaveBeenCalledWith(
      expect.objectContaining({
        company: 2,
        name: '캘린더',
        description: '일정 관리',
        is_active: false,
      }),
    )
    expect(router.currentRoute.value.path).toBe('/admin/products')
  })

  it('asks to register a company first when there is none', async () => {
    knowledgeApi.listAllCompanies.mockResolvedValue([])
    const { wrapper } = await mountRoute(ProductFormView, { path: '/admin/products/new' })

    expect(wrapper.text()).toContain('회사를 등록')
    expect(wrapper.get('[data-test="save"]').attributes('disabled')).toBeDefined()
  })
})
