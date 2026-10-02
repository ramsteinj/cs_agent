import { defineStore } from 'pinia'

import * as chatApi from '@/api/chat'

const DEFAULT_BOT_NAME = '고객지원 챗봇'

export const useChatStore = defineStore('chat', {
  state: () => ({
    enabled: false,
    botName: DEFAULT_BOT_NAME,
    welcomeMessage: '',
    statusLoaded: false,
    statusError: false,
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
  },
})
