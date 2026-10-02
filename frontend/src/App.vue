<script setup>
import { onMounted } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

import LoginModal from '@/components/LoginModal.vue'
import ToastContainer from '@/components/ToastContainer.vue'
import { useAuthStore } from '@/stores/auth'
import { useChatStore } from '@/stores/chat'
import { useToastStore } from '@/stores/toast'

const auth = useAuthStore()
const chat = useChatStore()
const toast = useToastStore()
const route = useRoute()
const router = useRouter()

onMounted(() => {
  auth.init()
  chat.loadStatus()
})

async function logout() {
  await auth.logout().catch(() => {})
  toast.show('로그아웃되었습니다.')
  if (route.matched.some((record) => record.meta.requiresAdmin)) router.push('/')
}
</script>

<template>
  <div class="d-flex flex-column h-100">
    <nav class="navbar navbar-expand-md navbar-dark bg-primary">
      <div class="container-fluid">
        <RouterLink class="navbar-brand" to="/">{{ chat.botName }}</RouterLink>
        <button
          class="navbar-toggler"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#mainNav"
          aria-controls="mainNav"
          aria-expanded="false"
          aria-label="메뉴 열기"
        >
          <span class="navbar-toggler-icon"></span>
        </button>
        <div id="mainNav" class="collapse navbar-collapse">
          <ul class="navbar-nav ms-auto">
            <li v-if="auth.isAdmin" class="nav-item dropdown">
              <a
                id="userMenu"
                class="nav-link dropdown-toggle"
                href="#"
                role="button"
                data-bs-toggle="dropdown"
                aria-expanded="false"
                data-test="user-menu"
              >
                {{ auth.user.username }}
              </a>
              <ul class="dropdown-menu dropdown-menu-end" aria-labelledby="userMenu">
                <li><RouterLink class="dropdown-item" to="/admin">관리자 페이지</RouterLink></li>
                <li><hr class="dropdown-divider" /></li>
                <li>
                  <button class="dropdown-item" type="button" data-test="logout" @click="logout">
                    로그아웃
                  </button>
                </li>
              </ul>
            </li>
            <li v-else class="nav-item">
              <button
                class="btn btn-outline-light btn-sm"
                type="button"
                data-test="login-button"
                @click="auth.openLoginModal()"
              >
                관리자 로그인
              </button>
            </li>
          </ul>
        </div>
      </div>
    </nav>

    <main class="flex-grow-1">
      <RouterView />
    </main>

    <LoginModal />
    <ToastContainer />
  </div>
</template>
