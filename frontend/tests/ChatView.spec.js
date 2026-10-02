import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import ChatView from '@/views/ChatView.vue'
import { fetchHealth } from '@/api/health'

vi.mock('@/api/health', () => ({ fetchHealth: vi.fn() }))

describe('ChatView (Phase 1 health check)', () => {
  it('shows connected when /api/health returns ok', async () => {
    fetchHealth.mockResolvedValueOnce({ status: 'ok' })
    const wrapper = mount(ChatView)
    await flushPromises()

    expect(wrapper.get('[data-test="health"]').text()).toContain('정상')
  })

  it('shows an error when the server is unreachable', async () => {
    fetchHealth.mockRejectedValueOnce(new Error('network'))
    const wrapper = mount(ChatView)
    await flushPromises()

    expect(wrapper.get('[data-test="health"]').text()).toContain('연결할 수 없습니다')
  })
})
