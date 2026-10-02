import { computed, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'

const LEAVE_MESSAGE = '저장하지 않은 변경 사항이 있습니다. 페이지를 떠나시겠습니까?'

/**
 * Confirm before leaving a form with unsaved changes (specs/06 §5.4).
 * Call markClean(form) after loading or saving.
 */
export function useUnsavedGuard(form) {
  const snapshot = ref(JSON.stringify(form))
  const dirty = computed(() => JSON.stringify(form) !== snapshot.value)

  function markClean() {
    snapshot.value = JSON.stringify(form)
  }

  onBeforeRouteLeave(() => !dirty.value || window.confirm(LEAVE_MESSAGE))

  return { dirty, markClean }
}
