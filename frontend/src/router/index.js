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
      { path: '', redirect: '/admin/companies' },
      {
        path: 'companies',
        name: 'admin-companies',
        component: () => import('@/views/admin/CompanyListView.vue'),
      },
      {
        path: 'companies/new',
        name: 'admin-company-new',
        component: () => import('@/views/admin/CompanyFormView.vue'),
      },
      {
        path: 'companies/:id/edit',
        name: 'admin-company-edit',
        component: () => import('@/views/admin/CompanyFormView.vue'),
      },
      {
        path: 'products',
        name: 'admin-products',
        component: () => import('@/views/admin/ProductListView.vue'),
      },
      {
        path: 'products/new',
        name: 'admin-product-new',
        component: () => import('@/views/admin/ProductFormView.vue'),
      },
      {
        path: 'products/:id/edit',
        name: 'admin-product-edit',
        component: () => import('@/views/admin/ProductFormView.vue'),
      },
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
