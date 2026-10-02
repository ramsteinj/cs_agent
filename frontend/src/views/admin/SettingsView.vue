<script setup>
import { onMounted, reactive, ref } from 'vue'

import { getErrorMessage, getFieldErrors } from '@/api/client'
import * as knowledgeApi from '@/api/knowledge'
import * as settingsApi from '@/api/settings'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import LlmSettingsCard from '@/components/LlmSettingsCard.vue'
import LoadingButton from '@/components/LoadingButton.vue'
import RagSettingsCard from '@/components/RagSettingsCard.vue'
import { useAuthStore } from '@/stores/auth'
import { useChatStore } from '@/stores/chat'
import { useToastStore } from '@/stores/toast'

// Cards: LLM, chatbot settings, RAG settings, knowledge index, password (specs/06 §5.5).
const EXTRA_MAX = 2000

const auth = useAuthStore()
const chat = useChatStore()
const toast = useToastStore()

const settings = ref(null)
const loadError = ref('')

// --- Chatbot settings ----------------------------------------------------
const botForm = reactive({
  bot_name: '',
  welcome_message: '',
  extra_instructions: '',
})
const botErrors = ref({})
const savingBot = ref(false)

// --- Knowledge index -----------------------------------------------------
const stats = ref(null)
const reindexing = ref(false)
const confirmReindex = ref(false)

// --- Password ------------------------------------------------------------
const pwForm = reactive({ current: '', next: '', confirm: '' })
const pwErrors = ref({})
const pwGeneralError = ref('')
const savingPw = ref(false)

function applySettings(data) {
  settings.value = data
  Object.assign(botForm, {
    bot_name: data.bot_name,
    welcome_message: data.welcome_message,
    extra_instructions: data.extra_instructions,
  })
}

async function loadStats() {
  try {
    stats.value = await knowledgeApi.getStats()
  } catch {
    stats.value = null
  }
}

onMounted(async () => {
  loadStats()
  try {
    applySettings(await settingsApi.getSettings())
  } catch (err) {
    loadError.value = getErrorMessage(err)
  }
})

async function runReindex() {
  confirmReindex.value = false
  reindexing.value = true
  try {
    const { chunks } = await knowledgeApi.reindex()
    toast.show(`재색인이 완료되었습니다. (청크 ${chunks}개)`)
    loadStats()
  } catch (err) {
    toast.show(getErrorMessage(err), 'danger')
  } finally {
    reindexing.value = false
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
      <!-- 1. LLM provider, API Keys and models -->
      <LlmSettingsCard :settings="settings" @update:settings="applySettings" />

      <!-- 2. Chatbot settings -->
      <div class="card mb-4" data-test="bot-card">
        <div class="card-header">챗봇 설정</div>
        <form class="card-body" novalidate @submit.prevent="saveBotSettings">
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

    <!-- 3. RAG tuning (stored in the DB) -->
    <RagSettingsCard @reindexed="loadStats" />

    <!-- 4. Knowledge index -->
    <div class="card mb-4" data-test="index-card">
      <div class="card-header">지식 색인</div>
      <div class="card-body">
        <dl v-if="stats" class="row small mb-3" data-test="index-stats">
          <dt class="col-5">회사 / 제품</dt>
          <dd class="col-7">{{ stats.companies }} / {{ stats.products }}</dd>
          <dt class="col-5">청크</dt>
          <dd class="col-7">{{ stats.chunks }}</dd>
          <dt class="col-5">임베딩 모델</dt>
          <dd class="col-7 text-break">
            {{ stats.embedding_model }} ({{ stats.embedding_dim }}차원)
          </dd>
        </dl>
        <p class="small text-muted">
          모든 회사·제품 정보의 청크와 임베딩을 다시 생성합니다. 임베딩 모델을 바꾼 뒤 사용하세요.
        </p>
        <LoadingButton
          type="button"
          variant="outline-primary"
          :loading="reindexing"
          loading-text="재색인 중..."
          data-test="reindex"
          @click="confirmReindex = true"
        >
          전체 재색인
        </LoadingButton>
      </div>
    </div>

    <!-- 5. Password (available even if settings failed to load) -->
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
      :show="confirmReindex"
      title="전체 재색인"
      message="모든 회사·제품 정보를 다시 색인합니다. 데이터 양에 따라 시간이 걸릴 수 있습니다. 진행하시겠습니까?"
      confirm-text="재색인"
      variant="primary"
      @confirm="runReindex"
      @cancel="confirmReindex = false"
    />
  </div>
</template>

<style scoped>
.settings-view {
  max-width: 40rem;
}
</style>
