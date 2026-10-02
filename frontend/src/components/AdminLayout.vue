<script setup>
import { RouterLink, RouterView, useRoute } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()

const menus = [
  { to: '/admin/companies', label: '회사 관리' },
  { to: '/admin/products', label: '제품 관리' },
  { to: '/admin/settings', label: '시스템 설정' },
]

// Also highlight the menu on its sub pages (e.g. /admin/companies/new).
const isActive = (menu) => route.path.startsWith(menu.to)
</script>

<template>
  <div class="container-fluid py-3">
    <div v-if="auth.mustChangePassword" class="alert alert-warning" role="alert">
      기본 비밀번호를 사용하고 있습니다. 보안을 위해
      <RouterLink to="/admin/settings" class="alert-link">비밀번호를 변경</RouterLink>하세요.
    </div>
    <div class="row g-3">
      <nav class="col-md-3 col-lg-2" aria-label="관리자 메뉴">
        <div class="list-group">
          <RouterLink
            v-for="menu in menus"
            :key="menu.to"
            :to="menu.to"
            class="list-group-item list-group-item-action"
            :class="{ active: isActive(menu) }"
            :aria-current="isActive(menu) ? 'page' : undefined"
          >
            {{ menu.label }}
          </RouterLink>
        </div>
      </nav>
      <section class="col-md-9 col-lg-10">
        <RouterView />
      </section>
    </div>
  </div>
</template>
