import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import ChatView from '@/views/ChatView.vue'

export const routes = [
  { path: '/', name: 'chat', component: ChatView },
  {
    path: '/admin',
    component: () => import('@/components/AdminLayout.vue'),
    meta: { requiresAdmin: true },
    children: [
      // Becomes /admin/companies once Phase 4 adds the knowledge screens.
      { path: '', redirect: '/admin/settings' },
      {
        path: 'settings',
        name: 'admin-settings',
        component: () => import('@/views/admin/SettingsView.vue'),
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
  },
]

/** Unauthenticated access to admin pages: go home and open the login modal. */
export async function adminGuard(to) {
  if (!to.matched.some((record) => record.meta.requiresAdmin)) return true
  const auth = useAuthStore()
  await auth.init()
  if (auth.isAdmin) return true
  auth.openLoginModal(to.fullPath)
  return { path: '/' }
}

export function createAppRouter(history = createWebHistory()) {
  const router = createRouter({ history, routes })
  router.beforeEach(adminGuard)
  return router
}

export default createAppRouter()
