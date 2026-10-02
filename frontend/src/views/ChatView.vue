<script setup>
// Phase 3: status + disabled state. Sending and streaming answers come in Phase 5.
import { computed } from 'vue'

import ChatInput from '@/components/ChatInput.vue'
import { useChatStore } from '@/stores/chat'

const DISABLED_MESSAGE = '현재 상담 서비스를 준비 중입니다.'
const ERROR_MESSAGE = '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.'

// Status is loaded once by App.vue (and refreshed after admin setting changes).
const chat = useChatStore()

const inputDisabled = computed(() => !chat.statusLoaded || !chat.enabled)
const placeholder = computed(() =>
  chat.statusLoaded && !chat.enabled ? DISABLED_MESSAGE : '메시지를 입력하세요.',
)
</script>

<template>
  <div class="container py-3 d-flex flex-column chat-view">
    <h1 class="h5 mb-3">{{ chat.botName }}</h1>

    <div class="flex-grow-1 overflow-auto mb-3" aria-live="polite">
      <div v-if="!chat.statusLoaded" class="text-muted small" data-test="chat-loading">
        상담 서비스를 확인하는 중입니다...
      </div>
      <div v-else-if="chat.statusError" class="alert alert-danger" data-test="chat-notice">
        {{ ERROR_MESSAGE }}
      </div>
      <div v-else-if="!chat.enabled" class="alert alert-secondary" data-test="chat-notice">
        {{ DISABLED_MESSAGE }}
      </div>
      <div v-else class="d-flex" data-test="welcome">
        <div class="bg-light border rounded-3 px-3 py-2 chat-bubble">
          {{ chat.welcomeMessage }}
        </div>
      </div>
    </div>

    <ChatInput :disabled="inputDisabled" :placeholder="placeholder" />
  </div>
</template>

<style scoped>
.chat-view {
  height: 100%;
  max-width: 48rem;
}

.chat-bubble {
  max-width: 85%;
  white-space: pre-wrap;
}
</style>
