import { defineStore } from 'pinia'

import * as chatApi from '@/api/chat'

const DEFAULT_BOT_NAME = '고객지원 챗봇'
const SESSION_KEY = 'cs_agent_chat_session'
export const ERROR_MESSAGE = '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.'

let nextLocalId = 1

function readSessionId() {
  try {
    return sessionStorage.getItem(SESSION_KEY)
  } catch {
    return null
  }
}

function writeSessionId(id) {
  try {
    if (id) sessionStorage.setItem(SESSION_KEY, id)
    else sessionStorage.removeItem(SESSION_KEY)
  } catch {
    // storage unavailable: the conversation just won't survive a reload
  }
}

function makeMessage(role, content, extra = {}) {
  return { key: nextLocalId++, role, content, sources: [], status: 'ok', errorText: '', ...extra }
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    enabled: false,
    botName: DEFAULT_BOT_NAME,
    welcomeMessage: '',
    statusLoaded: false,
    statusError: false,
    sessionId: null,
    messages: [],
    streaming: false,
  }),

  actions: {
    /** GET /api/chat/status. Any failure keeps the chat disabled (specs/01 F-U2). */
    async loadStatus() {
      try {
        const data = await chatApi.fetchStatus()
        this.enabled = data.enabled
        this.botName = data.bot_name
        this.welcomeMessage = data.welcome_message
        this.statusError = false
      } catch {
        this.enabled = false
        this.statusError = true
      } finally {
        this.statusLoaded = true
      }
    },

    /** Restore this tab's conversation after a reload (sessionStorage keeps the id). */
    async restore() {
      const id = readSessionId()
      if (!id || this.messages.length) return
      try {
        const stored = await chatApi.fetchMessages(id)
        this.sessionId = id
        this.messages = stored.map((m) =>
          makeMessage(m.role, m.content, {
            id: m.id,
            sources: m.sources || [],
            status: m.status,
            errorText: m.status === 'error' ? ERROR_MESSAGE : '',
          }),
        )
      } catch {
        writeSessionId(null) // expired or unknown session: start fresh
      }
    },

    async ensureSession() {
      if (!this.sessionId) {
        this.sessionId = await chatApi.createSession()
        writeSessionId(this.sessionId)
      }
      return this.sessionId
    },

    /** Send a question and stream the answer into a new assistant message. */
    async send(text) {
      const question = text.trim()
      if (!question || this.streaming || !this.enabled) return

      this.messages.push(makeMessage('user', question))
      const answer = makeMessage('assistant', '', { status: 'streaming' })
      this.messages.push(answer)
      // Work on the reactive copy so updates re-render.
      const reply = this.messages[this.messages.length - 1]
      this.streaming = true

      try {
        await this.streamInto(reply, question, true)
      } finally {
        this.streaming = false
      }
    },

    async streamInto(reply, question, retryOnMissingSession) {
      const fail = (message) => {
        reply.status = 'error'
        reply.errorText = message || ERROR_MESSAGE
      }
      try {
        const sessionId = await this.ensureSession()
        await chatApi.streamMessage(sessionId, question, {
          onStart: (event) => {
            reply.id = event.message_id
          },
          onDelta: (event) => {
            reply.content += event.text
          },
          onDone: (event) => {
            if (event.replace_text !== undefined) reply.content = event.replace_text
            reply.sources = event.sources || []
            reply.status = 'ok'
          },
          onError: (event) => fail(event.message),
        })
        if (reply.status === 'streaming') fail() // stream ended without done/error
      } catch (error) {
        if (error.status === 404 && retryOnMissingSession) {
          // Session expired on the server: start a new one and resend once.
          this.sessionId = null
          writeSessionId(null)
          return this.streamInto(reply, question, false)
        }
        if (error.code === 'CHATBOT_DISABLED') {
          this.enabled = false
          this.loadStatus()
        }
        fail(error.status === 429 ? error.message : undefined)
      }
    },

    /** Remove a failed answer (and its question) and ask again. */
    async retry(reply) {
      if (this.streaming) return
      const index = this.messages.indexOf(reply)
      const question = index > 0 ? this.messages[index - 1] : null
      if (!question || question.role !== 'user') return
      this.messages.splice(index - 1, 2)
      await this.send(question.content)
    },

    /** "새 대화": forget the conversation; a new session is created on the next send. */
    reset() {
      if (this.streaming) return
      this.messages = []
      this.sessionId = null
      writeSessionId(null)
    },
  },
})
