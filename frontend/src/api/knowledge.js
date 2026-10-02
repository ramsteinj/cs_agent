import client from './client'

// --- Companies -------------------------------------------------------------
export async function listCompanies(params = {}) {
  const { data } = await client.get('/admin/companies', { params })
  return data
}

/** All companies for dropdowns (max page size 100). */
export async function listAllCompanies() {
  const { results } = await listCompanies({ page_size: 100 })
  return results
}

export async function getCompany(id) {
  const { data } = await client.get(`/admin/companies/${id}`)
  return data
}

export async function createCompany(payload) {
  const { data } = await client.post('/admin/companies', payload)
  return data
}

export async function updateCompany(id, payload) {
  const { data } = await client.put(`/admin/companies/${id}`, payload)
  return data
}

export async function deleteCompany(id) {
  await client.delete(`/admin/companies/${id}`)
}

// --- Products --------------------------------------------------------------
export async function listProducts(params = {}) {
  const { data } = await client.get('/admin/products', { params })
  return data
}

export async function listCategories() {
  const { data } = await client.get('/admin/products/categories')
  return data
}

export async function getProduct(id) {
  const { data } = await client.get(`/admin/products/${id}`)
  return data
}

export async function createProduct(payload) {
  const { data } = await client.post('/admin/products', payload)
  return data
}

export async function updateProduct(id, payload) {
  const { data } = await client.put(`/admin/products/${id}`, payload)
  return data
}

export async function deleteProduct(id) {
  await client.delete(`/admin/products/${id}`)
}

// --- Index -----------------------------------------------------------------
export async function reindex() {
  const { data } = await client.post('/admin/knowledge/reindex')
  return data
}

export async function getStats() {
  const { data } = await client.get('/admin/knowledge/stats')
  return data
}

// --- Product documents (Text / MS Word / PDF) ----------------------------------
export async function listProductDocuments(productId) {
  const { data } = await client.get(`/admin/products/${productId}/documents`)
  return data
}

export async function uploadProductDocument(productId, file) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await client.post(`/admin/products/${productId}/documents`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function deleteProductDocument(productId, documentId) {
  await client.delete(`/admin/products/${productId}/documents/${documentId}`)
}
