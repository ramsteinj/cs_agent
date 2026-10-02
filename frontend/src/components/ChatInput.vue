<script setup>
import { computed, nextTick, ref } from 'vue'

const MAX_ROWS = 5

const props = defineProps({
  disabled: { type: Boolean, default: false },
  /** A reply is being generated: typing is allowed, sending is not. */
  busy: { type: Boolean, default: false },
  placeholder: { type: String, default: '메시지를 입력하세요.' },
  maxLength: { type: Number, default: 1000 },
})

const emit = defineEmits(['send'])
const text = ref('')
const textarea = ref(null)

const canSend = computed(() => !props.disabled && !props.busy && text.value.trim().length > 0)

function resize() {
  const el = textarea.value
  if (!el) return
  el.style.height = 'auto'
  const lineHeight = parseFloat(getComputedStyle(el).lineHeight) || 24
  el.style.height = `${Math.min(el.scrollHeight, lineHeight * MAX_ROWS + 16)}px`
}

async function send() {
  if (!canSend.value) return
  emit('send', text.value.trim())
  text.value = ''
  await nextTick()
  resize()
}

function onKeydown(event) {
  if (event.key !== 'Enter' || event.shiftKey) return // Shift+Enter: newline
  // Korean IME: Enter while composing only commits the syllable (keyCode 229 on some browsers).
  if (event.isComposing || event.keyCode === 229) return
  event.preventDefault()
  send()
}
</script>

<template>
  <form class="chat-input" @submit.prevent="send">
    <div class="d-flex gap-2 align-items-end">
      <label for="chat-input" class="visually-hidden">메시지</label>
      <textarea
        id="chat-input"
        ref="textarea"
        v-model="text"
        class="form-control"
        rows="1"
        :maxlength="maxLength"
        :placeholder="placeholder"
        :disabled="disabled"
        aria-describedby="chat-input-counter"
        @input="resize"
        @keydown="onKeydown"
      ></textarea>
      <button type="submit" class="btn btn-primary text-nowrap" :disabled="!canSend">
        <span
          v-if="busy"
          class="spinner-border spinner-border-sm"
          role="status"
          aria-label="답변 생성 중"
        ></span>
        <template v-else>전송</template>
      </button>
    </div>
    <div id="chat-input-counter" class="form-text text-end" data-test="counter">
      {{ text.length }}/{{ maxLength }}
    </div>
  </form>
</template>

<style scoped>
textarea {
  resize: none;
  overflow-y: auto;
}
</style>
