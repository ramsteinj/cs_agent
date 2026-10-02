import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as settingsApi from '@/api/settings'
import RagSettingsCard from '@/components/RagSettingsCard.vue'

import { apiError } from './helpers'

vi.mock('@/api/settings')

const RAG = {
  embedding_model: 'intfloat/multilingual-e5-small',
  embedding_dim: 384,
  chunk_max_chars: 500,
  chunk_overlap_chars: 100,
  retrieval_top_k: 5,
  retrieval_max_distance: 0.6,
  search_with_previous_question: true,
  history_messages: 10,
  max_sources: 3,
  llm_max_output_tokens: 4096,
  reindexed_chunks: null,
}

async function mountCard() {
  settingsApi.getRagSettings.mockResolvedValue(RAG)
  const wrapper = mount(RagSettingsCard, { attachTo: document.body })
  await flushPromises()
  return wrapper
}

describe('RagSettingsCard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
    document.body.innerHTML = ''
  })

  it('shows the stored values', async () => {
    const wrapper = await mountCard()

    expect(wrapper.get('#rag-embedding_model').element.value).toBe(RAG.embedding_model)
    expect(wrapper.get('#rag-retrieval_top_k').element.value).toBe('5')
    expect(wrapper.text()).toContain('384차원')
  })

  it('saves retrieval settings without asking (no reindex)', async () => {
    settingsApi.updateRagSettings.mockResolvedValue({ ...RAG, retrieval_top_k: 8 })
    const wrapper = await mountCard()

    await wrapper.get('#rag-retrieval_top_k').setValue('8')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(settingsApi.updateRagSettings).toHaveBeenCalledWith(
      expect.objectContaining({ retrieval_top_k: 8 }),
    )
    expect(wrapper.emitted('reindexed')).toBeUndefined()
  })

  it('confirms before a change that reindexes, then reports it', async () => {
    settingsApi.updateRagSettings.mockResolvedValue({
      ...RAG,
      chunk_max_chars: 300,
      reindexed_chunks: 12,
    })
    const wrapper = await mountCard()

    await wrapper.get('#rag-chunk_max_chars').setValue('300')
    expect(wrapper.text()).toContain('저장하면 전체 재색인이 실행됩니다.')
    await wrapper.get('form').trigger('submit')
    expect(settingsApi.updateRagSettings).not.toHaveBeenCalled()

    await wrapper.get('[data-test="confirm"]').trigger('click')
    await flushPromises()

    expect(settingsApi.updateRagSettings).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('reindexed')).toHaveLength(1)
  })

  it('shows field errors from the server', async () => {
    settingsApi.updateRagSettings.mockRejectedValue(
      apiError(400, {
        code: 'VALIDATION_ERROR',
        message: '입력값을 확인해 주세요.',
        details: { retrieval_top_k: ['20 이하로 입력해 주세요.'] },
      }),
    )
    const wrapper = await mountCard()

    await wrapper.get('#rag-retrieval_top_k').setValue('30')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('#rag-retrieval_top_k').classes()).toContain('is-invalid')
    expect(wrapper.text()).toContain('20 이하로 입력해 주세요.')
  })
})
