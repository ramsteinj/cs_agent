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
  name: '',
  description: '',
  website: '',
  phone: '',
  email: '',
  address: '',
  business_hours: '',
  extra_info: '',
})
const { markClean } = useUnsavedGuard(form)

const errors = ref({})
const generalError = ref('')
const loading = ref(false)
const saving = ref(false)

onMounted(async () => {
  if (!isEdit.value) return
  loading.value = true
  try {
    const company = await knowledgeApi.getCompany(id.value)
    for (const key of Object.keys(form)) form[key] = company[key] ?? ''
    markClean()
  } catch (err) {
    generalError.value = getErrorMessage(err)
  } finally {
    loading.value = false
  }
})

async function save() {
  errors.value = {}
  generalError.value = ''
  saving.value = true
  try {
    if (isEdit.value) await knowledgeApi.updateCompany(id.value, { ...form })
    else await knowledgeApi.createCompany({ ...form })
    markClean()
    toast.show('저장되었습니다.')
    router.push('/admin/companies')
  } catch (err) {
    errors.value = getFieldErrors(err)
    if (!Object.keys(errors.value).length) generalError.value = getErrorMessage(err)
  } finally {
    saving.value = false
  }
}

const fields = [
  { key: 'website', label: '웹사이트', type: 'url', placeholder: 'https://' },
  { key: 'phone', label: '대표 연락처', type: 'tel' },
  { key: 'email', label: '이메일', type: 'email' },
  { key: 'address', label: '주소', type: 'text' },
  { key: 'business_hours', label: '운영 시간', type: 'text', placeholder: '평일 09:00-18:00' },
]
</script>

<template>
  <div class="form-view">
    <h1 class="h4 mb-3">{{ isEdit ? '회사 정보 수정' : '회사 등록' }}</h1>

    <div v-if="loading" class="text-muted">불러오는 중...</div>
    <form v-else novalidate @submit.prevent="save">
      <div v-if="generalError" class="alert alert-danger" role="alert">{{ generalError }}</div>

      <div class="mb-3">
        <label for="company-name" class="form-label">회사명 *</label>
        <input
          id="company-name"
          v-model="form.name"
          type="text"
          class="form-control"
          maxlength="200"
          :class="{ 'is-invalid': errors.name }"
        />
        <div class="invalid-feedback">{{ errors.name }}</div>
      </div>
      <div class="mb-3">
        <label for="company-description" class="form-label">소개 *</label>
        <textarea
          id="company-description"
          v-model="form.description"
          class="form-control"
          rows="4"
          :class="{ 'is-invalid': errors.description }"
        ></textarea>
        <div class="invalid-feedback">{{ errors.description }}</div>
      </div>
      <div class="row">
        <div v-for="field in fields" :key="field.key" class="col-md-6 mb-3">
          <label :for="`company-${field.key}`" class="form-label">{{ field.label }}</label>
          <input
            :id="`company-${field.key}`"
            v-model="form[field.key]"
            :type="field.type"
            :placeholder="field.placeholder"
            class="form-control"
            :class="{ 'is-invalid': errors[field.key] }"
          />
          <div class="invalid-feedback">{{ errors[field.key] }}</div>
        </div>
      </div>
      <div class="mb-3">
        <label for="company-extra_info" class="form-label">기타 안내</label>
        <textarea
          id="company-extra_info"
          v-model="form.extra_info"
          class="form-control"
          rows="5"
          placeholder="환불 정책, 자주 묻는 질문 등"
          :class="{ 'is-invalid': errors.extra_info }"
        ></textarea>
        <div class="invalid-feedback">{{ errors.extra_info }}</div>
      </div>

      <div class="d-flex gap-2">
        <LoadingButton
          :loading="saving"
          loading-text="저장 중... 임베딩 생성"
          :disabled="!form.name.trim() || !form.description.trim()"
          data-test="save"
        >
          저장
        </LoadingButton>
        <RouterLink to="/admin/companies" class="btn btn-outline-secondary">목록</RouterLink>
      </div>
    </form>
  </div>
</template>

<style scoped>
.form-view {
  max-width: 48rem;
}
</style>
