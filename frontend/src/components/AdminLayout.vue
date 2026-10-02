<script setup>
import { RouterLink, RouterView } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

// Company / product menus are added in Phase 4.
const menus = [{ to: '/admin/settings', label: '시스템 설정' }]
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
            active-class="active"
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
