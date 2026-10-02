<script setup>
import { useToastStore } from '@/stores/toast'

const toastStore = useToastStore()
</script>

<template>
  <div class="toast-container position-fixed bottom-0 end-0 p-3" aria-live="polite">
    <div
      v-for="toast in toastStore.toasts"
      :key="toast.id"
      class="toast show align-items-center border-0"
      :class="`text-white bg-${toast.variant}`"
      role="status"
    >
      <div class="d-flex">
        <div class="toast-body">{{ toast.message }}</div>
        <button
          type="button"
          class="btn-close btn-close-white me-2 m-auto"
          aria-label="닫기"
          @click="toastStore.dismiss(toast.id)"
        ></button>
      </div>
    </div>
  </div>
</template>
