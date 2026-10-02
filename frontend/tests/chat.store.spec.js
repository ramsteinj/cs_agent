import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as chatApi from '@/api/chat'
import { useChatStore } from '@/stores/chat'

vi.mock('@/api/chat', () => ({ fetchStatus: vi.fn() }))

describe('chat store status', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('applies the server status', async () => {
    chatApi.fetchStatus.mockResolvedValueOnce({
      enabled: true,
      bot_name: 'OK 상담봇',
      welcome_message: '안녕하세요',
    })
    const chat = useChatStore()

    await chat.loadStatus()

    expect(chat.enabled).toBe(true)
    expect(chat.botName).toBe('OK 상담봇')
    expect(chat.welcomeMessage).toBe('안녕하세요')
    expect(chat.statusLoaded).toBe(true)
  })

  it('stays disabled when the status request fails', async () => {
    chatApi.fetchStatus.mockRejectedValueOnce(new Error('network'))
    const chat = useChatStore()
    chat.enabled = true

    await chat.loadStatus()

    expect(chat.enabled).toBe(false)
    expect(chat.statusError).toBe(true)
    expect(chat.statusLoaded).toBe(true)
  })
})
