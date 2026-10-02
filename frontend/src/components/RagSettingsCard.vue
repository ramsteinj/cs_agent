<script setup>
// RAG tuning values stored in the DB (specs/05 §1.1, specs/06 §5.5 card 3).
import { computed, onMounted, reactive, ref } from 'vue'

import { getErrorMessage, getFieldErrors } from '@/api/client'
import * as settingsApi from '@/api/settings'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import LoadingButton from '@/components/LoadingButton.vue'
import { useToastStore } from '@/stores/toast'

const emit = defineEmits(['reindexed'])
const toast = useToastStore()

const REINDEX_FIELDS = ['embedding_model', 'chunk_max_chars', 'chunk_overlap_chars']
const NUMBER_FIELDS = [
  {
    key: 'chunk_max_chars',
    label: '청크 최대 길이(자)',
    min: 100,
    max: 4000,
    step: 50,
    help: '문서를 나누는 단위. 변경 시 전체 재색인',
  },
  {
    key: 'chunk_overlap_chars',
    label: '청크 겹침(자)',
    min: 0,
    max: 3999,
    step: 10,
    help: '이웃 청크와 겹치는 길이. 변경 시 전체 재색인',
  },
  {
    key: 'retrieval_top_k',
    label: '검색 청크 수 (Top-K)',
    min: 1,
    max: 20,
    step: 1,
    help: '질문마다 LLM에 넘길 문서 조각 수',
  },
  {
    key: 'retrieval_max_distance',
    label: '최대 거리',
    min: 0,
    max: 2,
    step: 0.01,
    help: '코사인 거리. 이보다 먼 문서는 제외',
  },
  {
    key: 'history_messages',
    label: '대화 기록 메시지 수',
    min: 0,
    max: 50,
    step: 1,
    help: 'LLM에 함께 보낼 이전 메시지 수 (0이면 사용 안 함)',
  },
  {
    key: 'max_sources',
    label: '출처 표시 개수',
    min: 0,
    max: 10,
    step: 1,
    help: '답변 아래 표시할 참고 회사·제품 수',
  },
  {
    key: 'llm_max_output_tokens',
    label: '답변 최대 출력 토큰',
    min: 256,
    max: 32000,
    step: 256,
    help: 'LLM 답변 길이 상한',
  },
]

const form = reactive({})
const saved = ref(null)
const embeddingDim = ref(null)
const errors = ref({})
const loadError = ref('')
const saving = ref(false)
const confirmReindex = ref(false)

function apply(data) {
  embeddingDim.value = data.embedding_dim
  const values = { ...data }
  delete values.embedding_dim
  delete values.reindexed_chunks
  Object.assign(form, values)
  saved.value = { ...values }
}

onMounted(async () => {
  try {
    apply(await settingsApi.getRagSettings())
  } catch (err) {
    loadError.value = getErrorMessage(err)
  }
})

const needsReindex = computed(
  () => saved.value && REINDEX_FIELDS.some((key) => form[key] !== saved.value[key]),
)

function submit() {
  if (needsReindex.value) confirmReindex.value = true
  else save()
}

async function save() {
  confirmReindex.value = false
  errors.value = {}
  saving.value = true
  try {
    const data = await settingsApi.updateRagSettings({ ...form })
    apply(data)
    if (data.reindexed_chunks !== null) {
      toast.show(`RAG 설정이 저장되고 재색인되었습니다. (청크 ${data.reindexed_chunks}개)`)
      emit('reindexed')
    } else {
      toast.show('RAG 설정이 저장되었습니다.')
    }
  } catch (err) {
    errors.value = getFieldErrors(err)
    if (!Object.keys(errors.value).length) toast.show(getErrorMessage(err), 'danger')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="card mb-4" data-test="rag-card">
    <div class="card-header">RAG 설정</div>
    <div v-if="loadError" class="card-body">
      <div class="alert alert-danger mb-0" role="alert">{{ loadError }}</div>
    </div>
    <div v-else-if="!saved" class="card-body text-muted">불러오는 중...</div>
    <form v-else class="card-body" novalidate @submit.prevent="submit">
      <div class="mb-3">
        <label for="rag-embedding_model" class="form-label">임베딩 모델</label>
        <input
          id="rag-embedding_model"
          v-model.trim="form.embedding_model"
          type="text"
          class="form-control"
          :class="{ 'is-invalid': errors.embedding_model }"
          aria-describedby="rag-embedding_model-help"
        />
        <div class="invalid-feedback">{{ errors.embedding_model }}</div>
        <div id="rag-embedding_model-help" class="form-text">
          sentence-transformers 모델 이름 ({{ embeddingDim }}차원만 가능). 변경 시 모델을 내려받고
          전체 재색인합니다.
        </div>
      </div>
      <div class="row">
        <div v-for="field in NUMBER_FIELDS" :key="field.key" class="col-sm-6 mb-3">
          <label :for="`rag-${field.key}`" class="form-label">{{ field.label }}</label>
          <input
            :id="`rag-${field.key}`"
            v-model.number="form[field.key]"
            type="number"
            class="form-control"
            :min="field.min"
            :max="field.max"
            :step="field.step"
            :class="{ 'is-invalid': errors[field.key] }"
            :aria-describedby="`rag-${field.key}-help`"
          />
          <div class="invalid-feedback">{{ errors[field.key] }}</div>
          <div :id="`rag-${field.key}-help`" class="form-text">
            {{ field.help }} ({{ field.min }}~{{ field.max }})
          </div>
        </div>
      </div>
      <div class="form-check form-switch mb-3">
        <input
          id="rag-search_with_previous_question"
          v-model="form.search_with_previous_question"
          class="form-check-input"
          type="checkbox"
          role="switch"
        />
        <label class="form-check-label" for="rag-search_with_previous_question">
          검색할 때 직전 질문도 함께 사용 (후속 질문 이해에 도움)
        </label>
      </div>
      <div v-if="needsReindex" class="alert alert-info py-2 small" role="status">
        저장하면 전체 재색인이 실행됩니다.
      </div>
      <LoadingButton
        :loading="saving"
        :loading-text="needsReindex ? '저장 및 재색인 중...' : '저장 중...'"
        data-test="save-rag"
      >
        저장
      </LoadingButton>
    </form>

    <ConfirmDialog
      :show="confirmReindex"
      title="RAG 설정 저장"
      message="임베딩 모델 또는 청크 설정이 바뀌어 전체 재색인이 실행됩니다. 데이터 양에 따라 시간이 걸릴 수 있습니다. 진행하시겠습니까?"
      confirm-text="저장 및 재색인"
      variant="primary"
      @confirm="save"
      @cancel="confirmReindex = false"
    />
  </div>
</template>
