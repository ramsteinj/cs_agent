<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { getErrorMessage, getFieldErrors } from '@/api/client'
import * as knowledgeApi from '@/api/knowledge'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import LoadingButton from '@/components/LoadingButton.vue'
import { useUnsavedGuard } from '@/composables/useUnsavedGuard'
import { useToastStore } from '@/stores/toast'

const route = useRoute()
const router = useRouter()
const toast = useToastStore()

// Set from the route when editing, or after the first save of a new product.
const productId = ref(route.params.id || null)
const isEdit = computed(() => Boolean(productId.value))

// --- Product documents (Text / MS Word / PDF, specs/06 §5.6) -------------------
const ACCEPTED = ['txt', 'docx', 'pdf']
const MAX_FILE_BYTES = 10 * 1024 * 1024
const documents = ref([])
const pendingFiles = ref([]) // { key, file, error }
const fileErrors = ref([])
const pendingDelete = ref(null)
let nextFileKey = 1

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
const { markClean } = useUnsavedGuard(form, () => pendingFiles.value.length > 0)

const companies = ref([])
const categories = ref([])
const errors = ref({})
const generalError = ref('')
const loading = ref(true)
const saving = ref(false)

onMounted(async () => {
  try {
    const [companyList, categoryList, product, documentList] = await Promise.all([
      knowledgeApi.listAllCompanies(),
      knowledgeApi.listCategories(),
      isEdit.value ? knowledgeApi.getProduct(productId.value) : Promise.resolve(null),
      isEdit.value ? knowledgeApi.listProductDocuments(productId.value) : Promise.resolve([]),
    ])
    documents.value = documentList || []
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

// Either a description or at least one document must carry the product information.
const hasContent = computed(
  () =>
    Boolean(form.description.trim()) || documents.value.length > 0 || pendingFiles.value.length > 0,
)
const canSave = computed(() => form.company !== '' && Boolean(form.name.trim()) && hasContent.value)

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function addFiles(event) {
  fileErrors.value = []
  for (const file of event.target.files) {
    const extension = file.name.split('.').pop().toLowerCase()
    if (!file.name.includes('.') || !ACCEPTED.includes(extension)) {
      fileErrors.value.push(`${file.name}: Text(.txt), Word(.docx), PDF 파일만 올릴 수 있습니다.`)
    } else if (file.size > MAX_FILE_BYTES) {
      fileErrors.value.push(`${file.name}: 10MB 이하 파일만 올릴 수 있습니다.`)
    } else {
      pendingFiles.value.push({ key: nextFileKey++, file, error: '' })
    }
  }
  event.target.value = '' // allow choosing the same file again
}

function removePending(item) {
  pendingFiles.value = pendingFiles.value.filter((p) => p !== item)
}

/** Upload queued files one by one; failed ones stay queued with their error. */
async function uploadPending() {
  let failed = 0
  for (const item of [...pendingFiles.value]) {
    item.error = ''
    try {
      documents.value.push(await knowledgeApi.uploadProductDocument(productId.value, item.file))
      removePending(item)
    } catch (err) {
      item.error = getErrorMessage(err)
      failed += 1
    }
  }
  return failed
}

async function confirmDeleteDocument() {
  const document = pendingDelete.value
  pendingDelete.value = null
  try {
    await knowledgeApi.deleteProductDocument(productId.value, document.id)
    documents.value = documents.value.filter((d) => d.id !== document.id)
    toast.show('문서를 삭제했습니다.')
  } catch (err) {
    toast.show(getErrorMessage(err), 'danger')
  }
}

async function save() {
  errors.value = {}
  generalError.value = ''
  saving.value = true
  try {
    if (isEdit.value) await knowledgeApi.updateProduct(productId.value, { ...form })
    else productId.value = (await knowledgeApi.createProduct({ ...form })).id
    markClean()
    const failed = await uploadPending()
    if (failed) {
      toast.show(`제품은 저장했지만 문서 ${failed}개를 올리지 못했습니다.`, 'warning')
      return
    }
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
    <h1 class="h4 mb-3">{{ route.params.id ? '제품 정보 수정' : '제품 등록' }}</h1>

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
        <label for="product-description" class="form-label">상세 설명</label>
        <textarea
          id="product-description"
          v-model="form.description"
          class="form-control"
          rows="5"
          :class="{ 'is-invalid': errors.description }"
        ></textarea>
        <div class="invalid-feedback">{{ errors.description }}</div>
        <div class="form-text">상세 설명 또는 아래 제품 문서 중 하나 이상이 필요합니다.</div>
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
      <fieldset class="border rounded p-3 mb-3" data-test="documents">
        <legend class="float-none w-auto px-1 fs-6 mb-0">제품 문서 (Text / Word / PDF)</legend>
        <p class="form-text mt-0">
          .txt, .docx, .pdf 파일에서 텍스트를 추출해 제품 정보로 사용합니다. (파일당 10MB, 스캔한
          이미지 PDF·구형 .doc 제외)
        </p>

        <ul v-if="documents.length" class="list-group mb-2" data-test="document-list">
          <li
            v-for="doc in documents"
            :key="doc.id"
            class="list-group-item d-flex align-items-center gap-2"
          >
            <span class="badge bg-secondary text-uppercase">{{ doc.file_type }}</span>
            <span class="text-break flex-grow-1">{{ doc.file_name }}</span>
            <small class="text-muted text-nowrap">
              {{ formatSize(doc.file_size) }} · {{ doc.char_count.toLocaleString() }}자
            </small>
            <button
              type="button"
              class="btn btn-outline-danger btn-sm"
              :aria-label="`${doc.file_name} 삭제`"
              data-test="delete-document"
              @click="pendingDelete = doc"
            >
              삭제
            </button>
          </li>
        </ul>

        <ul v-if="pendingFiles.length" class="list-group mb-2" data-test="pending-list">
          <li v-for="item in pendingFiles" :key="item.key" class="list-group-item">
            <div class="d-flex align-items-center gap-2">
              <span class="badge bg-info text-dark">저장 시 업로드</span>
              <span class="text-break flex-grow-1">{{ item.file.name }}</span>
              <small class="text-muted text-nowrap">{{ formatSize(item.file.size) }}</small>
              <button
                type="button"
                class="btn btn-outline-secondary btn-sm"
                :aria-label="`${item.file.name} 제외`"
                @click="removePending(item)"
              >
                제외
              </button>
            </div>
            <div v-if="item.error" class="text-danger small mt-1" data-test="upload-error">
              {{ item.error }}
            </div>
          </li>
        </ul>

        <label for="product-files" class="form-label small mb-1">파일 추가</label>
        <input
          id="product-files"
          type="file"
          class="form-control"
          accept=".txt,.docx,.pdf"
          multiple
          @change="addFiles"
        />
        <div v-for="message in fileErrors" :key="message" class="text-danger small mt-1">
          {{ message }}
        </div>
      </fieldset>

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

    <ConfirmDialog
      :show="!!pendingDelete"
      title="문서 삭제"
      :message="
        pendingDelete
          ? `'${pendingDelete.file_name}' 문서를 삭제하시겠습니까? 이 문서의 내용은 챗봇 답변에 더 이상 사용되지 않습니다.`
          : ''
      "
      confirm-text="삭제"
      @confirm="confirmDeleteDocument"
      @cancel="pendingDelete = null"
    />
  </div>
</template>

<style scoped>
.form-view {
  max-width: 48rem;
}
</style>
