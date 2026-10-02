<script setup>
import { computed } from 'vue'

import { renderMarkdown } from '@/utils/markdown'

const props = defineProps({
  message: { type: Object, required: true },
})
defineEmits(['retry'])

const isUser = computed(() => props.message.role === 'user')
const isTyping = computed(() => props.message.status === 'streaming' && !props.message.content)
const isError = computed(() => props.message.status === 'error')
const sourceTitles = computed(() => props.message.sources.map((s) => s.title).join(', '))
// Bot answers are Markdown rendered to sanitized HTML; the customer's own text stays plain.
const answerHtml = computed(() => (isUser.value ? '' : renderMarkdown(props.message.content)))
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
      <span v-if="isTyping" class="typing" aria-label="답변 생성 중" data-test="typing">
        <span></span><span></span><span></span>
      </span>
      <div v-else-if="message.content && isUser" class="content">{{ message.content }}</div>
      <!-- eslint-disable-next-line vue/no-v-html -- DOMPurify-sanitized (utils/markdown.js) -->
      <div
        v-else-if="message.content"
        class="markdown"
        data-test="markdown"
        v-html="answerHtml"
      ></div>

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

.markdown {
  word-break: break-word;
}

.markdown :deep(p),
.markdown :deep(ul),
.markdown :deep(ol),
.markdown :deep(blockquote),
.markdown :deep(pre),
.markdown :deep(table) {
  margin-bottom: 0.5rem;
}

.markdown :deep(> :last-child) {
  margin-bottom: 0;
}

.markdown :deep(ul),
.markdown :deep(ol) {
  padding-left: 1.25rem;
}

.markdown :deep(h1),
.markdown :deep(h2),
.markdown :deep(h3),
.markdown :deep(h4),
.markdown :deep(h5),
.markdown :deep(h6) {
  font-size: 1rem;
  font-weight: 600;
  margin: 0.25rem 0;
}

.markdown :deep(pre) {
  white-space: pre-wrap;
  background: rgba(0, 0, 0, 0.05);
  padding: 0.5rem;
  border-radius: 0.25rem;
}

.markdown :deep(table) {
  font-size: 0.875rem;
  border-collapse: collapse;
}

.markdown :deep(th),
.markdown :deep(td) {
  border: 1px solid #dee2e6;
  padding: 0.25rem 0.5rem;
}

.markdown :deep(blockquote) {
  border-left: 3px solid #ced4da;
  padding-left: 0.5rem;
  color: #6c757d;
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
