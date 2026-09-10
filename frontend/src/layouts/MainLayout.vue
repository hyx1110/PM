<script setup lang="ts">
import AppSidebar from '@/components/layout/AppSidebar.vue'
import AppHeader from '@/components/layout/AppHeader.vue'
import AppBreadcrumb from '@/components/layout/AppBreadcrumb.vue'
</script>

<template>
  <div class="app-frame">
    <AppSidebar />
    <AppHeader />
    <main class="content">
      <AppBreadcrumb />
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in"><component :is="Component" /></transition>
      </router-view>
    </main>
  </div>
</template>

<style scoped>
.app-frame { min-height: 100vh; }
.content { min-height: 100vh; margin-left: 232px; padding: 86px 28px 32px; }
.fade-enter-active,.fade-leave-active { transition: opacity .16s ease, transform .16s ease; }
.fade-enter-from,.fade-leave-to { opacity: 0; transform: translateY(3px); }
</style>

