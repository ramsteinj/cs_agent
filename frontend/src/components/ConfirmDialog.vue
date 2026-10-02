<script setup>
import { nextTick, ref, watch } from 'vue'

const props = defineProps({
  show: { type: Boolean, default: false },
  title: { type: String, default: '확인' },
  message: { type: String, required: true },
  confirmText: { type: String, default: '확인' },
  variant: { type: String, default: 'danger' },
})

const emit = defineEmits(['confirm', 'cancel'])

// Move keyboard focus into the dialog so Enter/Esc work right away (specs/06 §7).
const cancelButton = ref(null)
watch(
  () => props.show,
  async (show) => {
    if (!show) return
    await nextTick()
    cancelButton.value?.focus()
  },
  { immediate: true },
)
</script>

<template>
  <template v-if="show">
    <div
      class="modal d-block"
      tabindex="-1"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirmDialogTitle"
      @keydown.esc="emit('cancel')"
    >
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h2 id="confirmDialogTitle" class="modal-title h5">{{ title }}</h2>
            <button
              type="button"
              class="btn-close"
              aria-label="닫기"
              @click="emit('cancel')"
            ></button>
          </div>
          <div class="modal-body">{{ message }}</div>
          <div class="modal-footer">
            <button
              ref="cancelButton"
              type="button"
              class="btn btn-outline-secondary"
              @click="emit('cancel')"
            >
              취소
            </button>
            <button
              type="button"
              class="btn"
              :class="`btn-${variant}`"
              data-test="confirm"
              @click="emit('confirm')"
            >
              {{ confirmText }}
            </button>
          </div>
        </div>
      </div>
    </div>
    <div class="modal-backdrop show"></div>
  </template>
</template>
