<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { ArrowDown, Bell } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useNotificationStore } from '@/stores/notification'

const router = useRouter()
const userStore = useUserStore()
const notificationStore = useNotificationStore()
const roleNames: Record<string, string> = {
  super_admin: '超级管理员',
  department_manager: 'L3',
  functional_manager: 'L4',
  project_manager: '项目经理',
  project_member: '项目成员',
}
const primaryRoleName = computed(() => {
  const role = userStore.profile?.roles?.[0]
  return role ? roleNames[role] || role : '用户'
})

async function handleCommand(command: string) {
  if (command === 'logout') {
    await userStore.logout()
    await router.push('/login')
  }
}

onMounted(async () => {
  if (!userStore.hasPermission('notification:view')) return
  await notificationStore.refreshUnreadCount()
})
</script>

<template>
  <header class="app-header">
    <div class="workspace-label">项目任务与人力协同管理系统</div>
    <div class="header-actions">
      <el-badge v-if="userStore.hasPermission('notification:view')" :value="notificationStore.unreadCount" :hidden="!notificationStore.unreadCount" :max="99">
        <button class="notice-button" title="通知中心" @click="router.push('/notifications')"><el-icon><Bell /></el-icon></button>
      </el-badge>
    <el-dropdown trigger="click" @command="handleCommand">
      <button class="user-button">
        <span class="avatar">{{ userStore.profile?.name?.slice(0, 1) || '用' }}</span>
        <span class="identity">
          <strong>{{ userStore.profile?.name }}</strong>
          <small>{{ primaryRoleName }}</small>
        </span>
        <el-icon><ArrowDown /></el-icon>
      </button>
      <template #dropdown>
        <el-dropdown-menu><el-dropdown-item command="logout">退出登录</el-dropdown-item></el-dropdown-menu>
      </template>
    </el-dropdown>
    </div>
  </header>
</template>

<style scoped>
.app-header { position: fixed; inset: 0 0 auto 232px; z-index: 15; display: flex; height: 64px; align-items: center; justify-content: space-between; border-bottom: 1px solid rgba(228,232,237,.9); background: rgba(244,246,248,.9); padding: 0 28px; backdrop-filter: blur(16px); }
.workspace-label { color: #818b9b; font-size: 13px; }
.header-actions { display: flex; align-items: center; gap: 20px; }
.notice-button { display: grid; width: 34px; height: 34px; place-items: center; border: 1px solid #e0e5ea; border-radius: 10px; background: #fff; color: #6f7d8f; cursor: pointer; }
.user-button { display: flex; align-items: center; gap: 10px; border: 0; background: transparent; color: #526071; cursor: pointer; }
.avatar { display: grid; width: 34px; height: 34px; place-items: center; border-radius: 50%; background: #dde7f1; color: #315f8e; font-weight: 700; }
.identity { display: flex; min-width: 80px; flex-direction: column; align-items: flex-start; }
.identity strong { color: #293548; font-size: 13px; font-weight: 600; }
.identity small { color: #a0a8b5; font-size: 10px; }
</style>
