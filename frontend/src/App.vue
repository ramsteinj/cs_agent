<script setup>
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="d-flex flex-column h-100">
    <nav class="navbar navbar-expand-md navbar-dark bg-primary">
      <div class="container-fluid">
        <RouterLink class="navbar-brand" to="/">고객지원 챗봇</RouterLink>
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
          <!-- Phase 2: admin login button / user menu (right aligned) -->
          <div class="ms-auto"></div>
        </div>
      </div>
    </nav>

    <main class="flex-grow-1">
      <RouterView />
    </main>
  </div>
</template>
