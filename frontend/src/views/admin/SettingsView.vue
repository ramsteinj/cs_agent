<script setup>
import { onMounted, reactive, ref } from 'vue'

import { getErrorMessage, getFieldErrors } from '@/api/client'
import * as settingsApi from '@/api/settings'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import LoadingButton from '@/components/LoadingButton.vue'
import { useAuthStore } from '@/stores/auth'
import { useChatStore } from '@/stores/chat'
import { useToastStore } from '@/stores/toast'

// Cards: API Key, chatbot settings, password. The knowledge index card follows in Phase 4.
const EXTRA_MAX = 2000

const auth = useAuthStore()
const chat = useChatStore()
const toast = useToastStore()

const settings = ref(null)
const loadError = ref('')

// --- API Key -------------------------------------------------------------
const apiKeyInput = ref('')
const apiKeyError = ref('')
const savingKey = ref(false)
const deletingKey = ref(false)
const confirmDelete = ref(false)

// --- Chatbot settings ----------------------------------------------------
const botForm = reactive({
  claude_model: '',
  bot_name: '',
  welcome_message: '',
  extra_instructions: '',
})
const botErrors = ref({})
const savingBot = ref(false)

// --- Password ------------------------------------------------------------
const pwForm = reactive({ current: '', next: '', confirm: '' })
const pwErrors = ref({})
const pwGeneralError = ref('')
const savingPw = ref(false)

function applySettings(data) {
  settings.value = data
  Object.assign(botForm, {
    claude_model: data.claude_model,
    bot_name: data.bot_name,
    welcome_message: data.welcome_message,
    extra_instructions: data.extra_instructions,
  })
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString('ko-KR') : ''
}

onMounted(async () => {
  try {
    applySettings(await settingsApi.getSettings())
  } catch (err) {
    loadError.value = getErrorMessage(err)
  }
})

async function saveApiKey() {
  apiKeyError.value = ''
  savingKey.value = true
  try {
    applySettings(await settingsApi.saveApiKey(apiKeyInput.value.trim()))
    toast.show('API Key가 저장되었습니다.')
    chat.loadStatus()
  } catch (err) {
    apiKeyError.value = getFieldErrors(err).api_key || getErrorMessage(err)
  } finally {
    // Never keep the secret in the page after a save attempt (specs/07 §3).
    apiKeyInput.value = ''
    savingKey.value = false
  }
}

async function deleteApiKey() {
  confirmDelete.value = false
  deletingKey.value = true
  try {
    await settingsApi.deleteApiKey()
    applySettings(await settingsApi.getSettings())
    toast.show('API Key가 삭제되었습니다. 챗봇이 비활성화됩니다.', 'secondary')
    chat.loadStatus()
  } catch (err) {
    toast.show(getErrorMessage(err), 'danger')
  } finally {
    deletingKey.value = false
  }
}

async function saveBotSettings() {
  botErrors.value = {}
  savingBot.value = true
  try {
    applySettings(await settingsApi.updateSettings({ ...botForm }))
    toast.show('챗봇 설정이 저장되었습니다.')
    chat.loadStatus()
  } catch (err) {
    botErrors.value = getFieldErrors(err)
    if (!Object.keys(botErrors.value).length) toast.show(getErrorMessage(err), 'danger')
  } finally {
    savingBot.value = false
  }
}

async function changePassword() {
  pwErrors.value = {}
  pwGeneralError.value = ''
  if (pwForm.next !== pwForm.confirm) {
    pwErrors.value = { confirm: '새 비밀번호가 일치하지 않습니다.' }
    return
  }
  savingPw.value = true
  try {
    await auth.changePassword(pwForm.current, pwForm.next)
    Object.assign(pwForm, { current: '', next: '', confirm: '' })
    toast.show('비밀번호가 변경되었습니다.')
  } catch (err) {
    const fieldErrors = getFieldErrors(err)
    pwErrors.value = {
      current: fieldErrors.current_password,
      next: fieldErrors.new_password || fieldErrors.non_field_errors,
    }
    if (!pwErrors.value.current && !pwErrors.value.next) {
      pwGeneralError.value = getErrorMessage(err)
    }
  } finally {
    savingPw.value = false
  }
}
</script>

<template>
  <div class="settings-view">
    <h1 class="h4 mb-3">시스템 설정</h1>

    <div v-if="loadError" class="alert alert-danger" role="alert">{{ loadError }}</div>
    <div v-else-if="!settings" class="text-muted" data-test="settings-loading">
      <span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>
      설정을 불러오는 중입니다...
    </div>

    <template v-if="settings">
      <!-- 1. Claude API Key -->
      <div class="card mb-4" data-test="api-key-card">
        <div class="card-header d-flex align-items-center">
          Claude API Key
          <span
            class="badge ms-2"
            :class="settings.api_key_configured ? 'bg-success' : 'bg-secondary'"
            data-test="api-key-status"
          >
            {{ settings.api_key_configured ? '등록됨' : '미등록' }}
          </span>
        </div>
        <form class="card-body" novalidate @submit.prevent="saveApiKey">
          <div v-if="!settings.api_key_configured" class="alert alert-warning py-2" role="alert">
            API Key를 등록해야 챗봇이 활성화됩니다.
          </div>
          <p v-else class="mb-3 small">
            현재 키: <code data-test="api-key-masked">{{ settings.api_key_masked }}</code>
            <span class="text-muted ms-2"
              >({{ formatDate(settings.api_key_updated_at) }} 등록)</span
            >
          </p>
          <label for="api-key" class="form-label">
            {{ settings.api_key_configured ? '새 API Key' : 'API Key' }}
          </label>
          <input
            id="api-key"
            v-model="apiKeyInput"
            type="password"
            class="form-control"
            :class="{ 'is-invalid': apiKeyError }"
            autocomplete="off"
            placeholder="sk-ant-..."
          />
          <div class="invalid-feedback" data-test="api-key-error">{{ apiKeyError }}</div>
          <div class="form-text">저장 전에 Anthropic API로 키가 유효한지 확인합니다.</div>
          <div class="mt-3 d-flex gap-2">
            <LoadingButton
              :loading="savingKey"
              loading-text="검증 중..."
              :disabled="!apiKeyInput.trim()"
              data-test="save-api-key"
            >
              저장
            </LoadingButton>
            <LoadingButton
              v-if="settings.api_key_configured"
              type="button"
              variant="outline-danger"
              :loading="deletingKey"
              data-test="delete-api-key"
              @click="confirmDelete = true"
            >
              삭제
            </LoadingButton>
          </div>
        </form>
      </div>

      <!-- 2. Chatbot settings -->
      <div class="card mb-4" data-test="bot-card">
        <div class="card-header">챗봇 설정</div>
        <form class="card-body" novalidate @submit.prevent="saveBotSettings">
          <div class="mb-3">
            <label for="bot-model" class="form-label">Claude 모델</label>
            <select
              id="bot-model"
              v-model="botForm.claude_model"
              class="form-select"
              :class="{ 'is-invalid': botErrors.claude_model }"
            >
              <option v-for="model in settings.available_models" :key="model" :value="model">
                {{ model }}
              </option>
            </select>
            <div class="invalid-feedback">{{ botErrors.claude_model }}</div>
          </div>
          <div class="mb-3">
            <label for="bot-name" class="form-label">챗봇 이름 *</label>
            <input
              id="bot-name"
              v-model="botForm.bot_name"
              type="text"
              class="form-control"
              maxlength="100"
              :class="{ 'is-invalid': botErrors.bot_name }"
            />
            <div class="invalid-feedback">{{ botErrors.bot_name }}</div>
          </div>
          <div class="mb-3">
            <label for="bot-welcome" class="form-label">환영 메시지 *</label>
            <textarea
              id="bot-welcome"
              v-model="botForm.welcome_message"
              class="form-control"
              rows="2"
              maxlength="1000"
              :class="{ 'is-invalid': botErrors.welcome_message }"
            ></textarea>
            <div class="invalid-feedback">{{ botErrors.welcome_message }}</div>
          </div>
          <div class="mb-3">
            <label for="bot-extra" class="form-label">추가 지시사항</label>
            <textarea
              id="bot-extra"
              v-model="botForm.extra_instructions"
              class="form-control"
              rows="4"
              :maxlength="EXTRA_MAX"
              :class="{ 'is-invalid': botErrors.extra_instructions }"
              aria-describedby="bot-extra-help"
            ></textarea>
            <div class="invalid-feedback">{{ botErrors.extra_instructions }}</div>
            <div id="bot-extra-help" class="form-text d-flex justify-content-between">
              <span>답변 톤 등 시스템 프롬프트에 덧붙일 지시사항</span>
              <span data-test="extra-counter">
                {{ botForm.extra_instructions.length }}/{{ EXTRA_MAX }}
              </span>
            </div>
          </div>
          <LoadingButton
            :loading="savingBot"
            :disabled="!botForm.bot_name.trim() || !botForm.welcome_message.trim()"
            data-test="save-bot"
          >
            저장
          </LoadingButton>
        </form>
      </div>
    </template>

    <!-- 3. Password (available even if settings failed to load) -->
    <div class="card" data-test="password-card">
      <div class="card-header">비밀번호 변경</div>
      <form class="card-body" novalidate @submit.prevent="changePassword">
        <div v-if="pwGeneralError" class="alert alert-danger py-2" role="alert">
          {{ pwGeneralError }}
        </div>
        <div class="mb-3">
          <label for="pw-current" class="form-label">현재 비밀번호</label>
          <input
            id="pw-current"
            v-model="pwForm.current"
            type="password"
            class="form-control"
            :class="{ 'is-invalid': pwErrors.current }"
            autocomplete="current-password"
          />
          <div class="invalid-feedback">{{ pwErrors.current }}</div>
        </div>
        <div class="mb-3">
          <label for="pw-new" class="form-label">새 비밀번호</label>
          <input
            id="pw-new"
            v-model="pwForm.next"
            type="password"
            class="form-control"
            :class="{ 'is-invalid': pwErrors.next }"
            autocomplete="new-password"
          />
          <div class="invalid-feedback">{{ pwErrors.next }}</div>
          <div class="form-text">
            8자 이상, 숫자로만 구성되거나 흔한 비밀번호는 사용할 수 없습니다.
          </div>
        </div>
        <div class="mb-3">
          <label for="pw-confirm" class="form-label">새 비밀번호 확인</label>
          <input
            id="pw-confirm"
            v-model="pwForm.confirm"
            type="password"
            class="form-control"
            :class="{ 'is-invalid': pwErrors.confirm }"
            autocomplete="new-password"
          />
          <div class="invalid-feedback">{{ pwErrors.confirm }}</div>
        </div>
        <LoadingButton
          :loading="savingPw"
          :disabled="!pwForm.current || !pwForm.next || !pwForm.confirm"
          data-test="change-password"
        >
          변경
        </LoadingButton>
      </form>
    </div>

    <ConfirmDialog
      :show="confirmDelete"
      title="API Key 삭제"
      message="API Key를 삭제하면 고객 채팅이 즉시 비활성화됩니다. 삭제하시겠습니까?"
      confirm-text="삭제"
      @confirm="deleteApiKey"
      @cancel="confirmDelete = false"
    />
  </div>
</template>

<style scoped>
.settings-view {
  max-width: 40rem;
}
</style>
