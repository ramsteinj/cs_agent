<script setup>
// LLM provider selection + per-provider API Key and model (specs/06 §5.5 card 1).
import { computed, ref, watch } from 'vue'

import { getErrorMessage, getFieldErrors } from '@/api/client'
import * as settingsApi from '@/api/settings'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import LoadingButton from '@/components/LoadingButton.vue'
import { useChatStore } from '@/stores/chat'
import { useToastStore } from '@/stores/toast'

const props = defineProps({
  settings: { type: Object, required: true },
})
const emit = defineEmits(['update:settings'])

const chat = useChatStore()
const toast = useToastStore()

const tab = ref(props.settings.llm_provider)
const switching = ref(false)

const apiKeyInput = ref('')
const apiKeyError = ref('')
const savingKey = ref(false)
const deletingKey = ref(false)
const confirmDelete = ref(false)

const models = ref([])
const modelsError = ref('')
const loadingModels = ref(false)
const savingModel = ref(false)

const providers = computed(() => props.settings.providers)
const current = computed(() => providers.value.find((p) => p.provider === tab.value))
const active = computed(() =>
  providers.value.find((p) => p.provider === props.settings.llm_provider),
)
const ready = (p) => p.api_key_configured && Boolean(p.model)

function formatDate(value) {
  return value ? new Date(value).toLocaleString('ko-KR') : ''
}

function updated(data) {
  emit('update:settings', data)
  chat.loadStatus()
}

async function selectProvider(provider) {
  if (provider === props.settings.llm_provider) return
  switching.value = true
  try {
    updated(await settingsApi.updateSettings({ llm_provider: provider }))
    tab.value = provider
    const label = providers.value.find((p) => p.provider === provider).label
    toast.show(`${label}(으)로 답변하도록 변경했습니다.`)
  } catch (err) {
    toast.show(getErrorMessage(err), 'danger')
  } finally {
    switching.value = false
  }
}

async function loadModels() {
  models.value = []
  modelsError.value = ''
  const provider = current.value
  // Claude has a recommended list even without a key; others need the key first.
  if (!provider.api_key_configured && provider.provider !== 'anthropic') return
  loadingModels.value = true
  try {
    models.value = (await settingsApi.listProviderModels(provider.provider)).models
  } catch (err) {
    modelsError.value = getErrorMessage(err)
  } finally {
    loadingModels.value = false
  }
}

watch(
  () => [tab.value, current.value?.api_key_configured],
  () => {
    apiKeyInput.value = ''
    apiKeyError.value = ''
    loadModels()
  },
  { immediate: true },
)

const modelOptions = computed(() => {
  const model = current.value.model
  return model && !models.value.includes(model) ? [model, ...models.value] : models.value
})

async function saveKey() {
  apiKeyError.value = ''
  savingKey.value = true
  try {
    updated(await settingsApi.saveProviderKey(tab.value, apiKeyInput.value.trim()))
    toast.show(`${current.value.label} API Key가 저장되었습니다.`)
  } catch (err) {
    apiKeyError.value = getFieldErrors(err).api_key || getErrorMessage(err)
  } finally {
    // Never keep the secret in the page after a save attempt (specs/07 §3).
    apiKeyInput.value = ''
    savingKey.value = false
  }
}

async function deleteKey() {
  confirmDelete.value = false
  deletingKey.value = true
  try {
    await settingsApi.deleteProviderKey(tab.value)
    updated(await settingsApi.getSettings())
    toast.show('API Key가 삭제되었습니다.', 'secondary')
  } catch (err) {
    toast.show(getErrorMessage(err), 'danger')
  } finally {
    deletingKey.value = false
  }
}

async function saveModel(event) {
  const model = event.target.value
  if (!model || model === current.value.model) return
  savingModel.value = true
  try {
    await settingsApi.updateProviderModel(tab.value, model)
    updated(await settingsApi.getSettings())
    toast.show(`모델을 ${model}(으)로 변경했습니다.`)
  } catch (err) {
    toast.show(getErrorMessage(err), 'danger')
  } finally {
    savingModel.value = false
  }
}
</script>

<template>
  <div class="card mb-4" data-test="llm-card">
    <div class="card-header">LLM 연동</div>
    <div class="card-body">
      <fieldset class="mb-3">
        <legend class="form-label fs-6">답변에 사용할 LLM</legend>
        <div class="btn-group flex-wrap" role="radiogroup" aria-label="LLM 선택">
          <template v-for="p in providers" :key="p.provider">
            <input
              :id="`llm-${p.provider}`"
              type="radio"
              class="btn-check"
              name="llm-provider"
              :value="p.provider"
              :checked="settings.llm_provider === p.provider"
              :disabled="switching"
              @change="selectProvider(p.provider)"
            />
            <label class="btn btn-outline-primary" :for="`llm-${p.provider}`">
              {{ p.label }}
            </label>
          </template>
        </div>
      </fieldset>

      <div
        v-if="active && !ready(active)"
        class="alert alert-warning py-2"
        role="alert"
        data-test="not-ready"
      >
        {{ active.label }}의 API Key 또는 모델이 설정되지 않아 챗봇이 비활성화되어 있습니다.
      </div>

      <ul class="nav nav-tabs" role="tablist">
        <li v-for="p in providers" :key="p.provider" class="nav-item" role="presentation">
          <button
            type="button"
            class="nav-link"
            :class="{ active: tab === p.provider }"
            role="tab"
            :aria-selected="tab === p.provider"
            :data-test="`tab-${p.provider}`"
            @click="tab = p.provider"
          >
            {{ p.label }}
            <span v-if="settings.llm_provider === p.provider" class="badge bg-primary ms-1">
              사용 중
            </span>
          </button>
        </li>
      </ul>

      <div v-if="current" class="border border-top-0 rounded-bottom p-3" role="tabpanel">
        <div class="mb-2 d-flex align-items-center">
          <span class="me-2">API Key</span>
          <span
            class="badge"
            :class="current.api_key_configured ? 'bg-success' : 'bg-secondary'"
            data-test="key-status"
          >
            {{ current.api_key_configured ? '등록됨' : '미등록' }}
          </span>
        </div>
        <p v-if="current.api_key_configured" class="small mb-2">
          현재 키: <code data-test="key-masked">{{ current.api_key_masked }}</code>
          <span class="text-muted ms-2">({{ formatDate(current.api_key_updated_at) }} 등록)</span>
        </p>
        <form novalidate @submit.prevent="saveKey">
          <label :for="`api-key-${current.provider}`" class="visually-hidden">
            {{ current.label }} API Key
          </label>
          <div class="input-group" :class="{ 'has-validation': apiKeyError }">
            <input
              :id="`api-key-${current.provider}`"
              v-model="apiKeyInput"
              type="password"
              class="form-control"
              :class="{ 'is-invalid': apiKeyError }"
              autocomplete="off"
              :placeholder="`${current.label} API Key`"
              data-test="key-input"
            />
            <LoadingButton
              :loading="savingKey"
              loading-text="검증 중..."
              :disabled="!apiKeyInput.trim()"
              data-test="save-key"
            >
              저장
            </LoadingButton>
            <div class="invalid-feedback" data-test="key-error">{{ apiKeyError }}</div>
          </div>
          <div class="form-text">저장 전에 {{ current.label }} API로 키가 유효한지 확인합니다.</div>
        </form>
        <LoadingButton
          v-if="current.api_key_configured"
          type="button"
          variant="outline-danger"
          class="btn-sm mt-2"
          :loading="deletingKey"
          data-test="delete-key"
          @click="confirmDelete = true"
        >
          키 삭제
        </LoadingButton>

        <div class="mt-3">
          <label :for="`model-${current.provider}`" class="form-label">모델</label>
          <div v-if="loadingModels" class="text-muted small">모델 목록을 불러오는 중...</div>
          <div v-else-if="modelsError" class="text-danger small" role="alert">
            {{ modelsError }}
          </div>
          <div
            v-else-if="!current.api_key_configured && current.provider !== 'anthropic'"
            class="text-muted small"
          >
            API Key를 등록하면 사용할 수 있는 모델 목록이 표시됩니다.
          </div>
          <template v-else>
            <select
              :id="`model-${current.provider}`"
              class="form-select"
              :value="current.model"
              :disabled="savingModel"
              data-test="model-select"
              @change="saveModel"
            >
              <option v-if="!current.model" value="" disabled>모델을 선택하세요</option>
              <option v-for="m in modelOptions" :key="m" :value="m">
                {{ m }}{{ m === current.default_model ? ' (기본)' : '' }}
              </option>
            </select>
          </template>
        </div>
      </div>
    </div>

    <ConfirmDialog
      :show="confirmDelete"
      title="API Key 삭제"
      :message="`${current?.label} API Key를 삭제하시겠습니까? 사용 중인 LLM이면 고객 채팅이 즉시 비활성화됩니다.`"
      confirm-text="삭제"
      @confirm="deleteKey"
      @cancel="confirmDelete = false"
    />
  </div>
</template>
