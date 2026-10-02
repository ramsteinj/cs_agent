import client from './client'
import { createSseParser } from './sse'

export async function fetchStatus() {
  const { data } = await client.get('/chat/status')
  return data
}

export async function createSession() {
  const { data } = await client.post('/chat/sessions')
  return data.session_id
}

export async function fetchMessages(sessionId) {
  const { data } = await client.get(`/chat/sessions/${sessionId}/messages`)
  return data
}

/** Error thrown for non-2xx responses before streaming starts. */
export class ChatRequestError extends Error {
  constructor(status, code, message) {
    super(message)
    this.status = status
    this.code = code
  }
}

/**
 * POST /api/chat/messages and dispatch SSE events to handlers.
 * Uses fetch + ReadableStream because EventSource cannot send a POST body.
 * Resolves when the stream ends; rejects with ChatRequestError or a network error.
 */
export async function streamMessage(sessionId, message, handlers = {}, { signal } = {}) {
  const response = await fetch('/api/chat/messages', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ session_id: sessionId, message }),
    signal,
  })

  if (!response.ok) {
    let error = {}
    try {
      error = (await response.json()).error || {}
    } catch {
      // non-JSON error body
    }
    throw new ChatRequestError(response.status, error.code, error.message)
  }

  const parser = createSseParser((event) => {
    const handler = { start: 'onStart', delta: 'onDelta', done: 'onDone', error: 'onError' }[
      event.type
    ]
    if (handler && handlers[handler]) handlers[handler](event)
  })
  const reader = response.body.getReader()
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    parser.push(value)
  }
  parser.end()
}
