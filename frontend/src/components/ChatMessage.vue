<script setup>
import { computed } from 'vue'

const props = defineProps({
  message: { type: Object, required: true },
})
defineEmits(['retry'])

const isUser = computed(() => props.message.role === 'user')
const isTyping = computed(() => props.message.status === 'streaming' && !props.message.content)
const isError = computed(() => props.message.status === 'error')
const sourceTitles = computed(() => props.message.sources.map((s) => s.title).join(', '))
</script>

<template>
  <div class="d-flex mb-2" :class="isUser ? 'justify-content-end' : 'justify-content-start'">
    <div
      class="rounded-3 px-3 py-2 chat-bubble"
      :class="{
        'bg-primary text-white': isUser,
        'bg-light border': !isUser && !isError,
        'border border-danger bg-white': isError,
      }"
      :data-test="`message-${message.role}`"
    >
      <!-- Plain text only: LLM output is never rendered as HTML (specs/07 §5). -->
      <span v-if="isTyping" class="typing" aria-label="답변 생성 중" data-test="typing">
        <span></span><span></span><span></span>
      </span>
      <div v-else-if="message.content" class="content">{{ message.content }}</div>

      <div v-if="isError" class="text-danger small mt-1" data-test="message-error">
        {{ message.errorText }}
        <button
          type="button"
          class="btn btn-link btn-sm p-0 ms-1 align-baseline"
          data-test="retry"
          @click="$emit('retry', message)"
        >
          다시 시도
        </button>
      </div>
      <div
        v-if="!isUser && message.status === 'ok' && message.sources.length"
        class="small text-muted mt-1"
        data-test="sources"
      >
        참고: {{ sourceTitles }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-bubble {
  max-width: 85%;
}

.content {
  white-space: pre-wrap;
  word-break: break-word;
}

.typing span {
  display: inline-block;
  width: 0.4rem;
  height: 0.4rem;
  margin: 0 0.1rem;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.4;
  animation: blink 1.2s infinite;
}

.typing span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes blink {
  50% {
    opacity: 1;
  }
}
</style>
