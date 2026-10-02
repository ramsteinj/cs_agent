import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h } from 'vue'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'

const Stub = defineComponent({ render: () => h('div', 'stub') })

/**
 * Mount `component` at `path` inside a RouterView, so useRoute/onBeforeRouteLeave work.
 * `pattern` is the route definition (e.g. '/admin/companies/:id/edit').
 */
export async function mountRoute(component, { path, pattern = path } = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: pattern, component },
      { path: '/:rest(.*)*', component: Stub },
    ],
  })
  await router.push(path)
  await router.isReady()
  const App = defineComponent({ render: () => h(RouterView) })
  const wrapper = mount(App, { global: { plugins: [pinia, router] }, attachTo: document.body })
  await flushPromises()
  return { wrapper, router }
}

export function apiError(status, error) {
  return { response: { status, data: { error } } }
}
