<script setup>
// Phase 1 placeholder: verifies the SPA -> Django connection.
// Replaced by the chat UI in Phase 3/5 (specs/06-frontend.md §5.1).
import { onMounted, ref } from 'vue'

import { fetchHealth } from '@/api/health'

const status = ref('checking') // checking | ok | error

onMounted(async () => {
  try {
    const data = await fetchHealth()
    status.value = data.status === 'ok' ? 'ok' : 'error'
  } catch {
    status.value = 'error'
  }
})
</script>

<template>
  <div class="container py-5">
    <h1 class="h4 mb-3">고객지원 챗봇</h1>
    <p v-if="status === 'checking'" class="text-muted" data-test="health">
      서버 연결을 확인하는 중입니다...
    </p>
    <div v-else-if="status === 'ok'" class="alert alert-success" data-test="health">
      서버 연결: 정상
    </div>
    <div v-else class="alert alert-danger" data-test="health">서버에 연결할 수 없습니다.</div>
  </div>
</template>
