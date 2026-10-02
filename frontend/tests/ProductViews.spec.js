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

describe('ProductFormView documents (Text / Word / PDF)', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    document.body.innerHTML = ''
    knowledgeApi.listAllCompanies.mockResolvedValue(COMPANIES)
    knowledgeApi.listCategories.mockResolvedValue([])
    knowledgeApi.listProductDocuments.mockResolvedValue([])
  })

  function pick(wrapper, files) {
    const input = wrapper.get('#product-files')
    Object.defineProperty(input.element, 'files', { value: files, configurable: true })
    return input.trigger('change')
  }

  const pdf = () => new File(['%PDF-1.4'], '가격표.pdf', { type: 'application/pdf' })

  async function newProduct() {
    const mounted = await mountRoute(ProductFormView, {
      path: '/admin/products/new?company=1',
      pattern: '/admin/products/new',
    })
    await mounted.wrapper.get('#product-name').setValue('문서 제품')
    return mounted
  }

  it('saves a product with only a document (no description)', async () => {
    knowledgeApi.createProduct.mockResolvedValue({ id: 9 })
    knowledgeApi.uploadProductDocument.mockResolvedValue({ id: 1, file_name: '가격표.pdf' })
    const { wrapper, router } = await newProduct()

    expect(wrapper.get('[data-test="save"]').attributes('disabled')).toBeDefined()
    const file = pdf()
    await pick(wrapper, [file])
    expect(wrapper.get('[data-test="pending-list"]').text()).toContain('가격표.pdf')
    expect(wrapper.get('[data-test="save"]').attributes('disabled')).toBeUndefined()

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(knowledgeApi.createProduct).toHaveBeenCalledWith(
      expect.objectContaining({ name: '문서 제품', description: '' }),
    )
    expect(knowledgeApi.uploadProductDocument).toHaveBeenCalledWith(9, file, '')
    expect(router.currentRoute.value.path).toBe('/admin/products')
  })

  it('rejects unsupported or too large files in the browser', async () => {
    const { wrapper } = await newProduct()
    const big = new File(['x'], 'big.pdf')
    Object.defineProperty(big, 'size', { value: 11 * 1024 * 1024 })

    await pick(wrapper, [new File(['x'], 'old.doc'), big])

    expect(wrapper.text()).toContain('old.doc: Text(.txt), Word(.docx), PDF 파일만')
    expect(wrapper.text()).toContain('big.pdf: 10MB 이하')
    expect(wrapper.find('[data-test="pending-list"]').exists()).toBe(false)
  })

  it('keeps failed uploads with their error and retries them on the next save', async () => {
    knowledgeApi.createProduct.mockResolvedValue({ id: 9 })
    knowledgeApi.updateProduct.mockResolvedValue({ id: 9 })
    knowledgeApi.uploadProductDocument
      .mockRejectedValueOnce({
        response: {
          status: 400,
          data: {
            error: {
              code: 'DOCUMENT_PARSE_ERROR',
              message: '파일에서 텍스트를 찾을 수 없습니다.',
            },
          },
        },
      })
      .mockResolvedValueOnce({ id: 1, file_name: '가격표.pdf' })
    const { wrapper, router } = await newProduct()
    await pick(wrapper, [pdf()])

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/admin/products/new')
    expect(wrapper.get('[data-test="upload-error"]').text()).toBe(
      '파일에서 텍스트를 찾을 수 없습니다.',
    )

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(knowledgeApi.createProduct).toHaveBeenCalledTimes(1) // second save updates
    expect(knowledgeApi.updateProduct).toHaveBeenCalledWith(9, expect.any(Object))
    expect(router.currentRoute.value.path).toBe('/admin/products')
  })

  it('lists and deletes existing documents when editing', async () => {
    knowledgeApi.getProduct.mockResolvedValue({
      id: 5,
      company: 1,
      name: '드라이브',
      category: '',
      summary: '',
      description: '',
      price: '',
      features: '',
      usage_guide: '',
      faq: '',
      is_active: true,
    })
    knowledgeApi.listProductDocuments.mockResolvedValue([
      {
        id: 3,
        title: '',
        display_name: '요금.docx',
        file_name: '요금.docx',
        file_type: 'docx',
        file_size: 2048,
        char_count: 1200,
      },
    ])
    knowledgeApi.deleteProductDocument.mockResolvedValue()
    const { wrapper } = await mountRoute(ProductFormView, {
      path: '/admin/products/5/edit',
      pattern: '/admin/products/:id/edit',
    })

    expect(wrapper.get('[data-test="document-list"]').text()).toContain('요금.docx')
    expect(wrapper.get('[data-test="document-list"]').text()).toContain('1,200자')

    await wrapper.get('[data-test="delete-document"]').trigger('click')
    await wrapper.get('[data-test="confirm"]').trigger('click')
    await flushPromises()

    expect(knowledgeApi.deleteProductDocument).toHaveBeenCalledWith('5', 3)
    expect(wrapper.find('[data-test="document-list"]').exists()).toBe(false)
  })
})

describe('ProductFormView document titles', () => {
  const EDIT_PRODUCT = {
    id: 5,
    company: 1,
    name: '오케이드라이브',
    category: '',
    summary: '',
    description: '',
    price: '',
    features: '',
    usage_guide: '',
    faq: '',
    is_active: true,
  }

  beforeEach(() => {
    vi.resetAllMocks()
    document.body.innerHTML = ''
    knowledgeApi.listAllCompanies.mockResolvedValue(COMPANIES)
    knowledgeApi.listCategories.mockResolvedValue([])
    knowledgeApi.getProduct.mockResolvedValue(EDIT_PRODUCT)
  })

  async function mountEdit(documents) {
    knowledgeApi.listProductDocuments.mockResolvedValue(documents)
    return mountRoute(ProductFormView, {
      path: '/admin/products/5/edit',
      pattern: '/admin/products/:id/edit',
    })
  }

  it('uploads several files for one product, each with its own title', async () => {
    knowledgeApi.updateProduct.mockResolvedValue({ id: 5 })
    knowledgeApi.uploadProductDocument.mockImplementation(async (_id, file, title) => ({
      id: file.name.length,
      title,
      display_name: title || file.name,
      file_name: file.name,
      file_type: 'pdf',
      file_size: 1,
      char_count: 1,
    }))
    const { wrapper } = await mountEdit([])
    const manual = new File(['%PDF'], 'manual.pdf')
    const guide = new File(['%PDF'], 'install.pdf')
    const input = wrapper.get('#product-files')
    Object.defineProperty(input.element, 'files', { value: [manual, guide], configurable: true })
    await input.trigger('change')

    const titles = wrapper.findAll('[data-test="pending-title"]')
    expect(titles[0].attributes('list')).toBe('document-title-options')
    await titles[0].setValue('사용자 매뉴얼')
    await titles[1].setValue('빠른 설치 가이드')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(knowledgeApi.uploadProductDocument.mock.calls.map((c) => c.slice(1))).toEqual([
      [manual, '사용자 매뉴얼'],
      [guide, '빠른 설치 가이드'],
    ])
  })

  it('suggests common document types', async () => {
    const { wrapper } = await mountEdit([])

    const options = wrapper
      .findAll('#document-title-options option')
      .map((o) => o.attributes('value'))
    expect(options).toContain('사용자 매뉴얼')
    expect(options).toContain('빠른 설치 가이드')
  })

  it('shows the title with the file name and renames a document', async () => {
    knowledgeApi.updateDocumentTitle.mockResolvedValue({
      id: 3,
      title: '빠른 설치 가이드',
      display_name: '빠른 설치 가이드',
      file_name: 'install.pdf',
      file_type: 'pdf',
      file_size: 10,
      char_count: 5,
    })
    const { wrapper } = await mountEdit([
      {
        id: 3,
        title: '',
        display_name: 'install.pdf',
        file_name: 'install.pdf',
        file_type: 'pdf',
        file_size: 10,
        char_count: 5,
      },
    ])
    const save = () => wrapper.get('[data-test="save-document-title"]')
    expect(save().attributes('disabled')).toBeDefined()

    await wrapper.get('[data-test="document-title"]').setValue('빠른 설치 가이드')
    expect(save().attributes('disabled')).toBeUndefined()
    await save().trigger('click')
    await flushPromises()

    expect(knowledgeApi.updateDocumentTitle).toHaveBeenCalledWith('5', 3, '빠른 설치 가이드')
    const list = wrapper.get('[data-test="document-list"]').text()
    expect(list).toContain('빠른 설치 가이드')
    expect(list).toContain('install.pdf')
    expect(save().attributes('disabled')).toBeDefined()
  })
})
