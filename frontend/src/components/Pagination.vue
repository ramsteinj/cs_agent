<script setup>
import { computed } from 'vue'

const props = defineProps({
  count: { type: Number, required: true },
  page: { type: Number, required: true },
  pageSize: { type: Number, default: 20 },
})
const emit = defineEmits(['update:page'])

const totalPages = computed(() => Math.max(1, Math.ceil(props.count / props.pageSize)))

// At most 5 page links around the current page.
const pages = computed(() => {
  const start = Math.max(1, Math.min(props.page - 2, totalPages.value - 4))
  const end = Math.min(totalPages.value, start + 4)
  return Array.from({ length: end - start + 1 }, (_, i) => start + i)
})

function go(page) {
  if (page >= 1 && page <= totalPages.value && page !== props.page) emit('update:page', page)
}
</script>

<template>
  <nav v-if="totalPages > 1" aria-label="페이지 이동">
    <ul class="pagination pagination-sm justify-content-center mb-0">
      <li class="page-item" :class="{ disabled: page === 1 }">
        <button class="page-link" type="button" aria-label="이전 페이지" @click="go(page - 1)">
          &laquo;
        </button>
      </li>
      <li v-for="p in pages" :key="p" class="page-item" :class="{ active: p === page }">
        <button
          class="page-link"
          type="button"
          :aria-current="p === page ? 'page' : undefined"
          @click="go(p)"
        >
          {{ p }}
        </button>
      </li>
      <li class="page-item" :class="{ disabled: page === totalPages }">
        <button class="page-link" type="button" aria-label="다음 페이지" @click="go(page + 1)">
          &raquo;
        </button>
      </li>
    </ul>
  </nav>
</template>
