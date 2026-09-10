<script setup lang="ts">
import { ArrowDown } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

async function handleCommand(command: string) {
  if (command === 'logout') {
    await userStore.logout()
    await router.push('/login')
  }
}
</script>

<template>
  <header class="app-header">
    <div class="workspace-label">项目任务与人力协同管理系统</div>
    <el-dropdown trigger="click" @command="handleCommand">
      <button class="user-button">
        <span class="avatar">{{ userStore.profile?.name?.slice(0, 1) || '用' }}</span>
        <span class="identity">
          <strong>{{ userStore.profile?.name }}</strong>
          <small>{{ userStore.profile?.roles?.[0] || 'user' }}</small>
        </span>
        <el-icon><ArrowDown /></el-icon>
      </button>
      <template #dropdown>
        <el-dropdown-menu><el-dropdown-item command="logout">退出登录</el-dropdown-item></el-dropdown-menu>
      </template>
    </el-dropdown>
  </header>
</template>

<style scoped>
.app-header { position: fixed; inset: 0 0 auto 232px; z-index: 15; display: flex; height: 64px; align-items: center; justify-content: space-between; border-bottom: 1px solid rgba(228,232,237,.9); background: rgba(244,246,248,.9); padding: 0 28px; backdrop-filter: blur(16px); }
.workspace-label { color: #818b9b; font-size: 13px; }
.user-button { display: flex; align-items: center; gap: 10px; border: 0; background: transparent; color: #526071; cursor: pointer; }
.avatar { display: grid; width: 34px; height: 34px; place-items: center; border-radius: 50%; background: #dde7f1; color: #315f8e; font-weight: 700; }
.identity { display: flex; min-width: 80px; flex-direction: column; align-items: flex-start; }
.identity strong { color: #293548; font-size: 13px; font-weight: 600; }
.identity small { color: #a0a8b5; font-size: 10px; }
</style>

