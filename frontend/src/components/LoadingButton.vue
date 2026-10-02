<script setup>
defineProps({
  loading: { type: Boolean, default: false },
  loadingText: { type: String, default: '' },
  type: { type: String, default: 'submit' },
  variant: { type: String, default: 'primary' },
  disabled: { type: Boolean, default: false },
})
</script>

<template>
  <button :type="type" class="btn" :class="`btn-${variant}`" :disabled="loading || disabled">
    <span
      v-if="loading"
      class="spinner-border spinner-border-sm me-1"
      role="status"
      aria-hidden="true"
    ></span>
    <template v-if="loading && loadingText">{{ loadingText }}</template>
    <slot v-else />
  </button>
</template>
