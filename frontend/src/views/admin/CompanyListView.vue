<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { getErrorMessage } from '@/api/client'
import * as knowledgeApi from '@/api/knowledge'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import Pagination from '@/components/Pagination.vue'
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()

const companies = ref([])
const count = ref(0)
const page = ref(1)
const search = ref('')
const loading = ref(false)
const error = ref('')
const pendingDelete = ref(null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = { page: page.value }
    if (search.value.trim()) params.search = search.value.trim()
    const data = await knowledgeApi.listCompanies(params)
    companies.value = data.results
    count.value = data.count
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    loading.value = false
  }
}

function applySearch() {
  page.value = 1
  load()
}

function changePage(next) {
  page.value = next
  load()
}

function deleteMessage(company) {
  const products = company.product_count
    ? ` 소속 제품 ${company.product_count}개도 함께 삭제됩니다.`
    : ''
  return `'${company.name}'을(를) 삭제하시겠습니까?${products}`
}

async function confirmDelete() {
  const company = pendingDelete.value
  pendingDelete.value = null
  try {
    await knowledgeApi.deleteCompany(company.id)
    toast.show('삭제되었습니다.')
    if (companies.value.length === 1 && page.value > 1) page.value -= 1
    load()
  } catch (err) {
    toast.show(getErrorMessage(err), 'danger')
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="d-flex align-items-center mb-3">
      <h1 class="h4 mb-0">회사 관리</h1>
      <RouterLink to="/admin/companies/new" class="btn btn-primary btn-sm ms-auto">
        새로 등록
      </RouterLink>
    </div>

    <form class="input-group mb-3" role="search" @submit.prevent="applySearch">
      <label for="company-search" class="visually-hidden">회사명 검색</label>
      <input
        id="company-search"
        v-model="search"
        type="search"
        class="form-control"
        placeholder="회사명 검색"
      />
      <button class="btn btn-outline-secondary" type="submit">검색</button>
    </form>

    <div v-if="error" class="alert alert-danger" role="alert">{{ error }}</div>

    <div class="table-responsive">
      <table class="table table-hover align-middle">
        <thead>
          <tr>
            <th scope="col">회사명</th>
            <th scope="col">연락처</th>
            <th scope="col" class="text-end">제품</th>
            <th scope="col" class="text-end">청크</th>
            <th scope="col" class="text-end">작업</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="5" class="text-center text-muted">불러오는 중...</td>
          </tr>
          <tr v-else-if="!companies.length">
            <td colspan="5" class="text-center text-muted" data-test="empty">
              등록된 회사가 없습니다.
            </td>
          </tr>
          <tr v-for="company in companies" v-else :key="company.id" data-test="company-row">
            <td>{{ company.name }}</td>
            <td class="small text-muted">{{ company.phone || company.email || '-' }}</td>
            <td class="text-end">{{ company.product_count }}</td>
            <td class="text-end">{{ company.chunk_count }}</td>
            <td class="text-end text-nowrap">
              <RouterLink
                :to="`/admin/companies/${company.id}/edit`"
                class="btn btn-outline-primary btn-sm me-1"
              >
                수정
              </RouterLink>
              <button
                type="button"
                class="btn btn-outline-danger btn-sm"
                data-test="delete"
                @click="pendingDelete = company"
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
      title="회사 삭제"
      :message="pendingDelete ? deleteMessage(pendingDelete) : ''"
      confirm-text="삭제"
      @confirm="confirmDelete"
      @cancel="pendingDelete = null"
    />
  </div>
</template>
