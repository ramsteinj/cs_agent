import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as chatApi from '@/api/chat'
import { ChatRequestError } from '@/api/chat'
import { ERROR_MESSAGE, useChatStore } from '@/stores/chat'

vi.mock('@/api/chat', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ChatRequestError: actual.ChatRequestError,
    fetchStatus: vi.fn(),
    createSession: vi.fn(),
    fetchMessages: vi.fn(),
    streamMessage: vi.fn(),
  }
})

/** streamMessage mock that replays SSE events through the handlers. */
function replay(events) {
  return async (_sessionId, _text, handlers) => {
    for (const event of events) {
      const name = { start: 'onStart', delta: 'onDelta', done: 'onDone', error: 'onError' }[
        event.type
      ]
      handlers[name]?.(event)
    }
  }
}

function enabledStore() {
  const chat = useChatStore()
  chat.enabled = true
  chat.statusLoaded = true
  return chat
}

describe('chat store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
    sessionStorage.clear()
    chatApi.createSession.mockResolvedValue('session-1')
  })

  describe('status', () => {
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
    })

    it('stays disabled when the status request fails', async () => {
      chatApi.fetchStatus.mockRejectedValueOnce(new Error('network'))
      const chat = useChatStore()
      chat.enabled = true

      await chat.loadStatus()

      expect(chat.enabled).toBe(false)
      expect(chat.statusError).toBe(true)
    })
  })

  describe('send', () => {
    it('streams deltas into an assistant message', async () => {
      chatApi.streamMessage.mockImplementation(
        replay([
          { type: 'start', message_id: 9 },
          { type: 'delta', text: '월 ' },
          { type: 'delta', text: '5,000원입니다.' },
          { type: 'done', sources: [{ type: 'product', id: 1, title: '드라이브' }] },
        ]),
      )
      const chat = enabledStore()

      await chat.send('  가격은?  ')

      expect(chatApi.streamMessage).toHaveBeenCalledWith('session-1', '가격은?', expect.any(Object))
      expect(sessionStorage.getItem('cs_agent_chat_session')).toBe('session-1')
      const [question, answer] = chat.messages
      expect(question).toMatchObject({ role: 'user', content: '가격은?' })
      expect(answer).toMatchObject({
        role: 'assistant',
        id: 9,
        content: '월 5,000원입니다.',
        status: 'ok',
      })
      expect(answer.sources[0].title).toBe('드라이브')
      expect(chat.streaming).toBe(false)
    })

    it('reuses the session for follow-up questions', async () => {
      chatApi.streamMessage.mockImplementation(replay([{ type: 'done', sources: [] }]))
      const chat = enabledStore()

      await chat.send('하나')
      await chat.send('둘')

      expect(chatApi.createSession).toHaveBeenCalledTimes(1)
    })

    it('replaces the streamed text when the server says so (refusal)', async () => {
      chatApi.streamMessage.mockImplementation(
        replay([
          { type: 'delta', text: '부분' },
          { type: 'done', sources: [], replace_text: '죄송합니다.' },
        ]),
      )
      const chat = enabledStore()

      await chat.send('q')

      expect(chat.messages[1].content).toBe('죄송합니다.')
    })

    it('marks the answer failed on an error event', async () => {
      chatApi.streamMessage.mockImplementation(
        replay([{ type: 'error', code: 'LLM_ERROR', message: ERROR_MESSAGE }]),
      )
      const chat = enabledStore()

      await chat.send('q')

      expect(chat.messages[1]).toMatchObject({ status: 'error', errorText: ERROR_MESSAGE })
    })

    it('marks the answer failed on a network error', async () => {
      chatApi.streamMessage.mockRejectedValueOnce(new TypeError('Failed to fetch'))
      const chat = enabledStore()

      await chat.send('q')

      expect(chat.messages[1]).toMatchObject({ status: 'error', errorText: ERROR_MESSAGE })
      expect(chat.streaming).toBe(false)
    })

    it('treats a stream that ends without done as an error', async () => {
      chatApi.streamMessage.mockImplementation(replay([{ type: 'delta', text: '끊김' }]))
      const chat = enabledStore()

      await chat.send('q')

      expect(chat.messages[1].status).toBe('error')
    })

    it('shows the server message on rate limit', async () => {
      chatApi.streamMessage.mockRejectedValueOnce(
        new ChatRequestError(429, 'RATE_LIMITED', '요청이 너무 많습니다.'),
      )
      const chat = enabledStore()

      await chat.send('q')

      expect(chat.messages[1].errorText).toBe('요청이 너무 많습니다.')
    })

    it('disables the chat when the server reports CHATBOT_DISABLED', async () => {
      chatApi.streamMessage.mockRejectedValueOnce(
        new ChatRequestError(503, 'CHATBOT_DISABLED', '준비 중'),
      )
      chatApi.fetchStatus.mockResolvedValue({ enabled: false, bot_name: 'x', welcome_message: '' })
      const chat = enabledStore()

      await chat.send('q')

      expect(chat.enabled).toBe(false)
    })

    it('starts a new session once when the old one is gone (404)', async () => {
      sessionStorage.setItem('cs_agent_chat_session', 'old')
      const chat = enabledStore()
      chat.sessionId = 'old'
      chatApi.streamMessage
        .mockRejectedValueOnce(new ChatRequestError(404, 'NOT_FOUND', ''))
        .mockImplementationOnce(replay([{ type: 'done', sources: [] }]))

      await chat.send('q')

      expect(chatApi.streamMessage.mock.calls.map((c) => c[0])).toEqual(['old', 'session-1'])
      expect(chat.messages[1].status).toBe('ok')
    })

    it('ignores blank input, disabled chat and concurrent sends', async () => {
      const chat = useChatStore()

      await chat.send('q') // disabled
      chat.enabled = true
      await chat.send('   ')
      chat.streaming = true
      await chat.send('q')

      expect(chatApi.streamMessage).not.toHaveBeenCalled()
      expect(chat.messages).toEqual([])
    })
  })

  it('retry removes the failed pair and asks again', async () => {
    chatApi.streamMessage
      .mockImplementationOnce(replay([{ type: 'error', code: 'LLM_ERROR', message: 'x' }]))
      .mockImplementationOnce(
        replay([
          { type: 'delta', text: '답' },
          { type: 'done', sources: [] },
        ]),
      )
    const chat = enabledStore()
    await chat.send('질문')

    await chat.retry(chat.messages[1])

    expect(chat.messages.map((m) => [m.role, m.content, m.status])).toEqual([
      ['user', '질문', 'ok'],
      ['assistant', '답', 'ok'],
    ])
  })

  it('reset clears messages and the session', async () => {
    chatApi.streamMessage.mockImplementation(replay([{ type: 'done', sources: [] }]))
    const chat = enabledStore()
    await chat.send('q')

    chat.reset()

    expect(chat.messages).toEqual([])
    expect(chat.sessionId).toBeNull()
    expect(sessionStorage.getItem('cs_agent_chat_session')).toBeNull()
  })

  describe('restore', () => {
    it('reloads the stored conversation', async () => {
      sessionStorage.setItem('cs_agent_chat_session', 's-9')
      chatApi.fetchMessages.mockResolvedValueOnce([
        { id: 1, role: 'user', content: '질문', status: 'ok' },
        { id: 2, role: 'assistant', content: '답', status: 'ok', sources: [{ title: 'A' }] },
      ])
      const chat = useChatStore()

      await chat.restore()

      expect(chat.sessionId).toBe('s-9')
      expect(chat.messages.map((m) => m.content)).toEqual(['질문', '답'])
      expect(chat.messages[1].sources).toEqual([{ title: 'A' }])
    })

    it('forgets an unknown session', async () => {
      sessionStorage.setItem('cs_agent_chat_session', 'gone')
      chatApi.fetchMessages.mockRejectedValueOnce({ response: { status: 404 } })
      const chat = useChatStore()

      await chat.restore()

      expect(chat.sessionId).toBeNull()
      expect(sessionStorage.getItem('cs_agent_chat_session')).toBeNull()
    })

    it('does nothing without a stored session', async () => {
      await useChatStore().restore()

      expect(chatApi.fetchMessages).not.toHaveBeenCalled()
    })
  })
})
