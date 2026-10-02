<script setup>
import { nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { getErrorMessage } from '@/api/client'
import LoadingButton from '@/components/LoadingButton.vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

const auth = useAuthStore()
const toast = useToastStore()
const router = useRouter()

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const usernameInput = ref(null)

watch(
  () => auth.loginModalOpen,
  async (open) => {
    if (!open) return
    username.value = ''
    password.value = ''
    error.value = ''
    await nextTick()
    usernameInput.value?.focus()
  },
)

function close() {
  if (loading.value) return
  auth.closeLoginModal()
}

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value.trim(), password.value)
    auth.closeLoginModal()
    toast.show('로그인되었습니다.')
    const redirect = auth.takeRedirectPath()
    if (redirect) router.push(redirect)
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <template v-if="auth.loginModalOpen">
    <div
      class="modal d-block"
      tabindex="-1"
      role="dialog"
      aria-modal="true"
      aria-labelledby="loginModalTitle"
      @keydown.esc="close"
    >
      <div class="modal-dialog modal-dialog-centered">
        <form class="modal-content" novalidate @submit.prevent="submit">
          <div class="modal-header">
            <h2 id="loginModalTitle" class="modal-title h5">관리자 로그인</h2>
            <button type="button" class="btn-close" aria-label="닫기" @click="close"></button>
          </div>
          <div class="modal-body">
            <div v-if="error" class="alert alert-danger py-2" role="alert" data-test="login-error">
              {{ error }}
            </div>
            <div class="mb-3">
              <label for="login-username" class="form-label">아이디</label>
              <input
                id="login-username"
                ref="usernameInput"
                v-model="username"
                type="text"
                class="form-control"
                autocomplete="username"
                required
              />
            </div>
            <div class="mb-1">
              <label for="login-password" class="form-label">비밀번호</label>
              <input
                id="login-password"
                v-model="password"
                type="password"
                class="form-control"
                autocomplete="current-password"
                required
              />
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-outline-secondary" @click="close">취소</button>
            <LoadingButton :loading="loading" :disabled="!username || !password">
              로그인
            </LoadingButton>
          </div>
        </form>
      </div>
    </div>
    <div class="modal-backdrop show"></div>
  </template>
</template>
