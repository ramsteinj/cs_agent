import { computed, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'

const LEAVE_MESSAGE = '저장하지 않은 변경 사항이 있습니다. 페이지를 떠나시겠습니까?'

/**
 * Confirm before leaving a form with unsaved changes (specs/06 §5.4).
 * Call markClean() after loading or saving. `extraDirty` covers state outside `form`
 * (e.g. files waiting to be uploaded).
 */
export function useUnsavedGuard(form, extraDirty = () => false) {
  const snapshot = ref(JSON.stringify(form))
  const dirty = computed(() => JSON.stringify(form) !== snapshot.value || extraDirty())

  function markClean() {
    snapshot.value = JSON.stringify(form)
  }

  onBeforeRouteLeave(() => !dirty.value || window.confirm(LEAVE_MESSAGE))

  return { dirty, markClean }
}
