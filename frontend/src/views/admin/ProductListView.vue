<script setup>
import { onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { getErrorMessage } from '@/api/client'
import * as knowledgeApi from '@/api/knowledge'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import Pagination from '@/components/Pagination.vue'
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()

const products = ref([])
const count = ref(0)
const page = ref(1)
const filters = reactive({ search: '', company: '', category: '', is_active: '' })
const companies = ref([])
const categories = ref([])
const loading = ref(false)
const error = ref('')
const pendingDelete = ref(null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = { page: page.value }
    for (const [key, value] of Object.entries(filters)) {
      if (String(value).trim()) params[key] = String(value).trim()
    }
    const data = await knowledgeApi.listProducts(params)
    products.value = data.results
    count.value = data.count
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    loading.value = false
  }
}

async function loadFilterOptions() {
  try {
    const [companyList, categoryList] = await Promise.all([
      knowledgeApi.listAllCompanies(),
      knowledgeApi.listCategories(),
    ])
    companies.value = companyList
    categories.value = categoryList
  } catch {
    // filters stay empty; the list itself still works
  }
}

function applyFilters() {
  page.value = 1
  load()
}

function changePage(next) {
  page.value = next
  load()
}

async function confirmDelete() {
  const product = pendingDelete.value
  pendingDelete.value = null
  try {
    await knowledgeApi.deleteProduct(product.id)
    toast.show('삭제되었습니다.')
    if (products.value.length === 1 && page.value > 1) page.value -= 1
    load()
  } catch (err) {
    toast.show(getErrorMessage(err), 'danger')
  }
}

onMounted(() => {
  load()
  loadFilterOptions()
})
</script>

<template>
  <div>
    <div class="d-flex align-items-center mb-3">
      <h1 class="h4 mb-0">제품 관리</h1>
      <RouterLink to="/admin/products/new" class="btn btn-primary btn-sm ms-auto">
        새로 등록
      </RouterLink>
    </div>

    <form class="row g-2 mb-3" role="search" @submit.prevent="applyFilters">
      <div class="col-12 col-md-4">
        <label for="product-search" class="visually-hidden">제품명 검색</label>
        <input
          id="product-search"
          v-model="filters.search"
          type="search"
          class="form-control"
          placeholder="제품명 검색"
        />
      </div>
      <div class="col-6 col-md-3">
        <label for="filter-company" class="visually-hidden">회사</label>
        <select
          id="filter-company"
          v-model="filters.company"
          class="form-select"
          @change="applyFilters"
        >
          <option value="">전체 회사</option>
          <option v-for="c in companies" :key="c.id" :value="String(c.id)">{{ c.name }}</option>
        </select>
      </div>
      <div class="col-6 col-md-2">
        <label for="filter-category" class="visually-hidden">카테고리</label>
        <select
          id="filter-category"
          v-model="filters.category"
          class="form-select"
          @change="applyFilters"
        >
          <option value="">전체 카테고리</option>
          <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
        </select>
      </div>
      <div class="col-6 col-md-2">
        <label for="filter-active" class="visually-hidden">판매 여부</label>
        <select
          id="filter-active"
          v-model="filters.is_active"
          class="form-select"
          @change="applyFilters"
        >
          <option value="">전체 상태</option>
          <option value="true">활성</option>
          <option value="false">비활성</option>
        </select>
      </div>
      <div class="col-6 col-md-1 d-grid">
        <button class="btn btn-outline-secondary" type="submit">검색</button>
      </div>
    </form>

    <div v-if="error" class="alert alert-danger" role="alert">{{ error }}</div>

    <div class="table-responsive">
      <table class="table table-hover align-middle">
        <thead>
          <tr>
            <th scope="col">제품명</th>
            <th scope="col" class="d-none d-md-table-cell">회사</th>
            <th scope="col" class="d-none d-md-table-cell">카테고리</th>
            <th scope="col" class="d-none d-md-table-cell">가격</th>
            <th scope="col">상태</th>
            <th scope="col" class="text-end d-none d-md-table-cell">문서</th>
            <th scope="col" class="text-end d-none d-md-table-cell">청크</th>
            <th scope="col" class="text-end">작업</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="8" class="text-center text-muted">불러오는 중...</td>
          </tr>
          <tr v-else-if="!products.length">
            <td colspan="8" class="text-center text-muted" data-test="empty">
              등록된 제품이 없습니다.
            </td>
          </tr>
          <tr v-for="product in products" v-else :key="product.id" data-test="product-row">
            <td>
              {{ product.name }}
              <!-- category is its own column on desktop; same-name products differ by it -->
              <div
                v-if="product.category"
                class="small text-muted d-md-none"
                data-test="row-category"
              >
                {{ product.category }}
              </div>
            </td>
            <td class="small d-none d-md-table-cell">{{ product.company_name }}</td>
            <td class="small d-none d-md-table-cell">{{ product.category || '-' }}</td>
            <td class="small d-none d-md-table-cell">{{ product.price || '-' }}</td>
            <td>
              <span class="badge" :class="product.is_active ? 'bg-success' : 'bg-secondary'">
                {{ product.is_active ? '활성' : '비활성' }}
              </span>
            </td>
            <td class="text-end d-none d-md-table-cell">{{ product.document_count }}</td>
            <td class="text-end d-none d-md-table-cell">{{ product.chunk_count }}</td>
            <td class="text-end text-nowrap">
              <RouterLink
                :to="`/admin/products/${product.id}/edit`"
                class="btn btn-outline-primary btn-sm me-1"
              >
                수정
              </RouterLink>
              <button
                type="button"
                class="btn btn-outline-danger btn-sm"
                data-test="delete"
                @click="pendingDelete = product"
              >
                삭제
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <Pagination :count="count" :page="page" @update:page="changePage" />

    <ConfirmDialog
      :show="!!pendingDelete"
      title="제품 삭제"
      :message="pendingDelete ? `'${pendingDelete.name}'을(를) 삭제하시겠습니까?` : ''"
      confirm-text="삭제"
      @confirm="confirmDelete"
      @cancel="pendingDelete = null"
    />
  </div>
</template>
