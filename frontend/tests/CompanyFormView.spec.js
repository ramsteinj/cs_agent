import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as knowledgeApi from '@/api/knowledge'
import CompanyFormView from '@/views/admin/CompanyFormView.vue'

import { apiError, mountRoute } from './helpers'

vi.mock('@/api/knowledge')

async function fillRequired(wrapper) {
  await wrapper.get('#company-name').setValue('오케이테크')
  await wrapper.get('#company-description').setValue('소개')
}

describe('CompanyFormView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    document.body.innerHTML = ''
  })
  afterEach(() => vi.restoreAllMocks())

  it('creates a company and returns to the list', async () => {
    knowledgeApi.createCompany.mockResolvedValue({ id: 1 })
    const { wrapper, router } = await mountRoute(CompanyFormView, {
      path: '/admin/companies/new',
    })

    await fillRequired(wrapper)
    await wrapper.get('#company-phone').setValue('02-123')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(knowledgeApi.createCompany).toHaveBeenCalledWith(
      expect.objectContaining({ name: '오케이테크', description: '소개', phone: '02-123' }),
    )
    expect(router.currentRoute.value.path).toBe('/admin/companies')
  })

  it('shows the duplicate-name error on the name field (409)', async () => {
    knowledgeApi.createCompany.mockRejectedValue(
      apiError(409, {
        code: 'CONFLICT',
        message: '이미 등록된 항목입니다.',
        details: { name: ['이미 등록된 회사명입니다.'] },
      }),
    )
    const { wrapper } = await mountRoute(CompanyFormView, { path: '/admin/companies/new' })

    await fillRequired(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('#company-name').classes()).toContain('is-invalid')
    expect(wrapper.text()).toContain('이미 등록된 회사명입니다.')
  })

  it('loads and updates an existing company', async () => {
    knowledgeApi.getCompany.mockResolvedValue({
      id: 7,
      name: '기존',
      description: '설명',
      website: '',
      phone: '',
      email: '',
      address: '',
      business_hours: '',
      extra_info: '',
    })
    knowledgeApi.updateCompany.mockResolvedValue({ id: 7 })
    const { wrapper } = await mountRoute(CompanyFormView, {
      path: '/admin/companies/7/edit',
      pattern: '/admin/companies/:id/edit',
    })

    expect(wrapper.get('#company-name').element.value).toBe('기존')
    await wrapper.get('#company-name').setValue('변경')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(knowledgeApi.updateCompany).toHaveBeenCalledWith(
      '7',
      expect.objectContaining({ name: '변경' }),
    )
  })

  it('asks before leaving with unsaved changes', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const { wrapper, router } = await mountRoute(CompanyFormView, {
      path: '/admin/companies/new',
    })

    await wrapper.get('#company-name').setValue('작성 중')
    await router.push('/admin/companies')

    expect(confirm).toHaveBeenCalled()
    expect(router.currentRoute.value.path).toBe('/admin/companies/new')
  })

  it('leaves without asking when nothing changed', async () => {
    const confirm = vi.spyOn(window, 'confirm')
    const { router } = await mountRoute(CompanyFormView, { path: '/admin/companies/new' })

    await router.push('/admin/companies')

    expect(confirm).not.toHaveBeenCalled()
    expect(router.currentRoute.value.path).toBe('/admin/companies')
  })
})
