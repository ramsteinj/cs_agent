<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { getErrorMessage, getFieldErrors } from '@/api/client'
import * as knowledgeApi from '@/api/knowledge'
import LoadingButton from '@/components/LoadingButton.vue'
import { useUnsavedGuard } from '@/composables/useUnsavedGuard'
import { useToastStore } from '@/stores/toast'

const route = useRoute()
const router = useRouter()
const toast = useToastStore()

const id = computed(() => route.params.id)
const isEdit = computed(() => Boolean(id.value))

const form = reactive({
  company: route.query.company ? Number(route.query.company) : '',
  name: '',
  category: '',
  summary: '',
  description: '',
  price: '',
  features: '',
  usage_guide: '',
  faq: '',
  is_active: true,
})
const { markClean } = useUnsavedGuard(form)

const companies = ref([])
const categories = ref([])
const errors = ref({})
const generalError = ref('')
const loading = ref(true)
const saving = ref(false)

onMounted(async () => {
  try {
    const [companyList, categoryList, product] = await Promise.all([
      knowledgeApi.listAllCompanies(),
      knowledgeApi.listCategories(),
      isEdit.value ? knowledgeApi.getProduct(id.value) : Promise.resolve(null),
    ])
    companies.value = companyList
    categories.value = categoryList
    if (product) {
      for (const key of Object.keys(form)) form[key] = product[key] ?? ''
    }
    markClean()
  } catch (err) {
    generalError.value = getErrorMessage(err)
  } finally {
    loading.value = false
  }
})

const canSave = computed(() => form.company !== '' && form.name.trim() && form.description.trim())

async function save() {
  errors.value = {}
  generalError.value = ''
  saving.value = true
  try {
    if (isEdit.value) await knowledgeApi.updateProduct(id.value, { ...form })
    else await knowledgeApi.createProduct({ ...form })
    markClean()
    toast.show('저장되었습니다.')
    router.push('/admin/products')
  } catch (err) {
    errors.value = getFieldErrors(err)
    if (!Object.keys(errors.value).length) generalError.value = getErrorMessage(err)
  } finally {
    saving.value = false
  }
}

const textareas = [
  { key: 'features', label: '주요 기능', rows: 4 },
  { key: 'usage_guide', label: '사용 방법', rows: 4 },
  { key: 'faq', label: 'FAQ', rows: 5 },
]
</script>

<template>
  <div class="form-view">
    <h1 class="h4 mb-3">{{ isEdit ? '제품 정보 수정' : '제품 등록' }}</h1>

    <div v-if="loading" class="text-muted">불러오는 중...</div>
    <form v-else novalidate @submit.prevent="save">
      <div v-if="generalError" class="alert alert-danger" role="alert">{{ generalError }}</div>
      <div v-if="!companies.length" class="alert alert-warning" role="alert">
        먼저 <RouterLink to="/admin/companies/new" class="alert-link">회사를 등록</RouterLink>해
        주세요.
      </div>

      <div class="row">
        <div class="col-md-6 mb-3">
          <label for="product-company" class="form-label">소속 회사 *</label>
          <select
            id="product-company"
            v-model="form.company"
            class="form-select"
            :class="{ 'is-invalid': errors.company }"
          >
            <option value="" disabled>선택하세요</option>
            <option v-for="c in companies" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
          <div class="invalid-feedback">{{ errors.company }}</div>
        </div>
        <div class="col-md-6 mb-3">
          <label for="product-name" class="form-label">제품명 *</label>
          <input
            id="product-name"
            v-model="form.name"
            type="text"
            class="form-control"
            maxlength="200"
            :class="{ 'is-invalid': errors.name }"
          />
          <div class="invalid-feedback">{{ errors.name }}</div>
        </div>
        <div class="col-md-6 mb-3">
          <label for="product-category" class="form-label">카테고리</label>
          <input
            id="product-category"
            v-model="form.category"
            type="text"
            class="form-control"
            maxlength="100"
            list="category-options"
            :class="{ 'is-invalid': errors.category }"
          />
          <datalist id="category-options">
            <option v-for="c in categories" :key="c" :value="c" />
          </datalist>
          <div class="invalid-feedback">{{ errors.category }}</div>
        </div>
        <div class="col-md-6 mb-3">
          <label for="product-price" class="form-label">가격</label>
          <input
            id="product-price"
            v-model="form.price"
            type="text"
            class="form-control"
            maxlength="100"
            placeholder="예: 월 9,900원"
            :class="{ 'is-invalid': errors.price }"
          />
          <div class="invalid-feedback">{{ errors.price }}</div>
        </div>
      </div>
      <div class="mb-3">
        <label for="product-summary" class="form-label">요약</label>
        <input
          id="product-summary"
          v-model="form.summary"
          type="text"
          class="form-control"
          maxlength="500"
          :class="{ 'is-invalid': errors.summary }"
        />
        <div class="invalid-feedback">{{ errors.summary }}</div>
      </div>
      <div class="mb-3">
        <label for="product-description" class="form-label">상세 설명 *</label>
        <textarea
          id="product-description"
          v-model="form.description"
          class="form-control"
          rows="5"
          :class="{ 'is-invalid': errors.description }"
        ></textarea>
        <div class="invalid-feedback">{{ errors.description }}</div>
      </div>
      <div v-for="field in textareas" :key="field.key" class="mb-3">
        <label :for="`product-${field.key}`" class="form-label">{{ field.label }}</label>
        <textarea
          :id="`product-${field.key}`"
          v-model="form[field.key]"
          class="form-control"
          :rows="field.rows"
          :class="{ 'is-invalid': errors[field.key] }"
        ></textarea>
        <div class="invalid-feedback">{{ errors[field.key] }}</div>
      </div>
      <div class="form-check form-switch mb-4">
        <input
          id="product-active"
          v-model="form.is_active"
          class="form-check-input"
          type="checkbox"
          role="switch"
        />
        <label class="form-check-label" for="product-active">
          판매 중 (비활성 제품은 챗봇 답변에 사용되지 않습니다)
        </label>
      </div>

      <div class="d-flex gap-2">
        <LoadingButton
          :loading="saving"
          loading-text="저장 중... 임베딩 생성"
          :disabled="!canSave"
          data-test="save"
        >
          저장
        </LoadingButton>
        <RouterLink to="/admin/products" class="btn btn-outline-secondary">목록</RouterLink>
      </div>
    </form>
  </div>
</template>

<style scoped>
.form-view {
  max-width: 48rem;
}
</style>
