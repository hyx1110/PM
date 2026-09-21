<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ArrowDown, Bell } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useNotificationStore } from '@/stores/notification'
import { changeCurrentPassword, updateCurrentUser } from '@/api/auth'

const router = useRouter()
const userStore = useUserStore()
const notificationStore = useNotificationStore()
const profileVisible = ref(false)
const passwordVisible = ref(false)
const saving = ref(false)
const profileForm = reactive({ name: '', email: '' })
const passwordForm = reactive({ current_password: '', new_password: '', confirm_password: '' })
const roleNames: Record<string, string> = {
  super_admin: '超级管理员',
  department_manager: '部门主管',
  functional_manager: '职能主管',
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
  if (command === 'profile') {
    Object.assign(profileForm, {
      name: userStore.profile?.name || '',
      email: userStore.profile?.email || '',
    })
    profileVisible.value = true
  }
  if (command === 'password') {
    Object.assign(passwordForm, { current_password: '', new_password: '', confirm_password: '' })
    passwordVisible.value = true
  }
}

async function saveProfile() {
  if (!profileForm.name.trim()) return ElMessage.warning('姓名不能为空')
  saving.value = true
  try {
    await updateCurrentUser({ name: profileForm.name.trim(), email: profileForm.email || null })
    await userStore.fetchProfile()
    profileVisible.value = false
    ElMessage.success('个人资料已更新')
  } finally { saving.value = false }
}

async function savePassword() {
  if (passwordForm.new_password.length < 8) return ElMessage.warning('新密码至少 8 位')
  if (passwordForm.new_password !== passwordForm.confirm_password) return ElMessage.warning('两次输入的新密码不一致')
  saving.value = true
  try {
    await changeCurrentPassword(passwordForm)
    passwordVisible.value = false
    ElMessage.success('登录密码已修改')
  } finally { saving.value = false }
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
        <el-dropdown-menu><el-dropdown-item command="profile">修改个人资料</el-dropdown-item><el-dropdown-item command="password">修改登录密码</el-dropdown-item><el-dropdown-item divided command="logout">退出登录</el-dropdown-item></el-dropdown-menu>
      </template>
    </el-dropdown>
    </div>
  </header>
  <el-dialog v-model="profileVisible" title="修改个人资料" width="460px">
    <el-form :model="profileForm" label-position="top"><el-form-item label="员工号 / 登录账号"><el-input :model-value="userStore.profile?.employee_no" disabled/></el-form-item><el-form-item label="姓名" required><el-input v-model="profileForm.name" maxlength="100"/></el-form-item><el-form-item label="邮箱"><el-input v-model="profileForm.email" type="email"/></el-form-item></el-form>
    <template #footer><el-button @click="profileVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="saveProfile">保存</el-button></template>
  </el-dialog>
  <el-dialog v-model="passwordVisible" title="修改登录密码" width="460px">
    <el-form :model="passwordForm" label-position="top"><el-form-item label="当前密码" required><el-input v-model="passwordForm.current_password" type="password" show-password/></el-form-item><el-form-item label="新密码" required><el-input v-model="passwordForm.new_password" type="password" show-password/></el-form-item><el-form-item label="确认新密码" required><el-input v-model="passwordForm.confirm_password" type="password" show-password/></el-form-item></el-form>
    <template #footer><el-button @click="passwordVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="savePassword">确认修改</el-button></template>
  </el-dialog>
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
