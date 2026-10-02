<script setup>
// Phase 3: disabled state. Enter/Shift+Enter, IME and the counter follow in Phase 5.
import { computed, ref } from 'vue'

const props = defineProps({
  disabled: { type: Boolean, default: false },
  placeholder: { type: String, default: '메시지를 입력하세요.' },
  maxLength: { type: Number, default: 1000 },
})

const emit = defineEmits(['send'])
const text = ref('')

const canSend = computed(() => !props.disabled && text.value.trim().length > 0)

function send() {
  if (!canSend.value) return
  emit('send', text.value.trim())
  text.value = ''
}
</script>

<template>
  <form class="d-flex gap-2" @submit.prevent="send">
    <label for="chat-input" class="visually-hidden">메시지</label>
    <textarea
      id="chat-input"
      v-model="text"
      class="form-control"
      rows="1"
      :maxlength="maxLength"
      :placeholder="placeholder"
      :disabled="disabled"
    ></textarea>
    <button type="submit" class="btn btn-primary" :disabled="!canSend" aria-label="전송">
      전송
    </button>
  </form>
</template>
