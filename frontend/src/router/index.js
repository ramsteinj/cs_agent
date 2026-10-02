import { createRouter, createWebHistory } from 'vue-router'

import ChatView from '@/views/ChatView.vue'

export const routes = [
  { path: '/', name: 'chat', component: ChatView },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
