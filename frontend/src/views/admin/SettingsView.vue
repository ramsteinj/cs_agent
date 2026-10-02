<script setup>
import { reactive, ref } from 'vue'

import { getErrorMessage, getFieldErrors } from '@/api/client'
import LoadingButton from '@/components/LoadingButton.vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

// Phase 2: password card only. API Key / chatbot / index cards follow in Phase 3-4.
const auth = useAuthStore()
const toast = useToastStore()

const form = reactive({ current: '', next: '', confirm: '' })
const errors = ref({})
const generalError = ref('')
const saving = ref(false)

async function changePassword() {
  errors.value = {}
  generalError.value = ''
  if (form.next !== form.confirm) {
    errors.value = { confirm: '새 비밀번호가 일치하지 않습니다.' }
    return
  }
  saving.value = true
  try {
    await auth.changePassword(form.current, form.next)
    Object.assign(form, { current: '', next: '', confirm: '' })
    toast.show('비밀번호가 변경되었습니다.')
  } catch (err) {
    const fieldErrors = getFieldErrors(err)
    errors.value = {
      current: fieldErrors.current_password,
      next: fieldErrors.new_password || fieldErrors.non_field_errors,
    }
    if (!errors.value.current && !errors.value.next) generalError.value = getErrorMessage(err)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div>
    <h1 class="h4 mb-3">시스템 설정</h1>

    <div class="card" style="max-width: 32rem">
      <div class="card-header">비밀번호 변경</div>
      <form class="card-body" novalidate @submit.prevent="changePassword">
        <div v-if="generalError" class="alert alert-danger py-2" role="alert">
          {{ generalError }}
        </div>
        <div class="mb-3">
          <label for="pw-current" class="form-label">현재 비밀번호</label>
          <input
            id="pw-current"
            v-model="form.current"
            type="password"
            class="form-control"
            :class="{ 'is-invalid': errors.current }"
            autocomplete="current-password"
          />
          <div class="invalid-feedback">{{ errors.current }}</div>
        </div>
        <div class="mb-3">
          <label for="pw-new" class="form-label">새 비밀번호</label>
          <input
            id="pw-new"
            v-model="form.next"
            type="password"
            class="form-control"
            :class="{ 'is-invalid': errors.next }"
            autocomplete="new-password"
          />
          <div class="invalid-feedback">{{ errors.next }}</div>
          <div class="form-text">
            8자 이상, 숫자로만 구성되거나 흔한 비밀번호는 사용할 수 없습니다.
          </div>
        </div>
        <div class="mb-3">
          <label for="pw-confirm" class="form-label">새 비밀번호 확인</label>
          <input
            id="pw-confirm"
            v-model="form.confirm"
            type="password"
            class="form-control"
            :class="{ 'is-invalid': errors.confirm }"
            autocomplete="new-password"
          />
          <div class="invalid-feedback">{{ errors.confirm }}</div>
        </div>
        <LoadingButton
          :loading="saving"
          :disabled="!form.current || !form.next || !form.confirm"
          data-test="change-password"
        >
          변경
        </LoadingButton>
      </form>
    </div>
  </div>
</template>
