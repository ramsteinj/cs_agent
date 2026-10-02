<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import ChatInput from '@/components/ChatInput.vue'
import ChatMessage from '@/components/ChatMessage.vue'
import { useChatStore } from '@/stores/chat'

const DISABLED_MESSAGE = '현재 상담 서비스를 준비 중입니다.'
const ERROR_MESSAGE = '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.'

// Status is loaded once by App.vue (and refreshed after admin setting changes).
const chat = useChatStore()
const scroller = ref(null)

onMounted(() => chat.restore())

const inputDisabled = computed(() => !chat.statusLoaded || !chat.enabled)
const placeholder = computed(() =>
  chat.statusLoaded && !chat.enabled ? DISABLED_MESSAGE : '메시지를 입력하세요.',
)

// Keep the newest message in view while answers stream in.
watch(
  () => [chat.messages.length, chat.messages.at(-1)?.content],
  async () => {
    await nextTick()
    if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
  },
)
</script>

<template>
  <div class="container py-3 d-flex flex-column chat-view">
    <div class="d-flex align-items-center mb-3">
      <h1 class="h5 mb-0">{{ chat.botName }}</h1>
      <button
        type="button"
        class="btn btn-outline-secondary btn-sm ms-auto"
        :disabled="chat.streaming || !chat.messages.length"
        data-test="new-chat"
        @click="chat.reset()"
      >
        새 대화
      </button>
    </div>

    <div ref="scroller" class="flex-grow-1 overflow-auto mb-2" aria-live="polite">
      <div v-if="!chat.statusLoaded" class="text-muted small" data-test="chat-loading">
        상담 서비스를 확인하는 중입니다...
      </div>
      <div v-else-if="chat.statusError" class="alert alert-danger" data-test="chat-notice">
        {{ ERROR_MESSAGE }}
      </div>
      <div v-else-if="!chat.enabled" class="alert alert-secondary" data-test="chat-notice">
        {{ DISABLED_MESSAGE }}
      </div>
      <template v-else>
        <div class="d-flex mb-2" data-test="welcome">
          <div class="bg-light border rounded-3 px-3 py-2 welcome-bubble">
            {{ chat.welcomeMessage }}
          </div>
        </div>
        <ChatMessage
          v-for="message in chat.messages"
          :key="message.key"
          :message="message"
          @retry="chat.retry"
        />
      </template>
    </div>

    <ChatInput
      :disabled="inputDisabled"
      :busy="chat.streaming"
      :placeholder="placeholder"
      @send="chat.send"
    />
  </div>
</template>

<style scoped>
.chat-view {
  height: 100%;
  max-width: 48rem;
}

.welcome-bubble {
  max-width: 85%;
  white-space: pre-wrap;
}
</style>
