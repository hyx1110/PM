<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  Calendar,
  Collection,
  DataAnalysis,
  Document,
  HomeFilled,
  OfficeBuilding,
  Tickets,
  UploadFilled,
  User,
  UserFilled,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const userStore = useUserStore()
const menuItems = computed(() => [
  { path: '/dashboard', label: '首页', icon: HomeFilled },
  { path: '/users', label: '用户管理', icon: User, permission: 'user:view' },
  { path: '/organizations', label: '组织管理', icon: OfficeBuilding, permission: 'organization:view' },
  { path: '/roles', label: '角色权限', icon: UserFilled, permission: 'role:view' },
  { path: '/projects', label: '项目管理', icon: Collection, permission: 'project:view' },
  { path: '/tasks', label: '任务管理', icon: Tickets, permission: 'task:view' },
  { path: '/schedules', label: '任务共享看板', icon: Calendar, permission: 'schedule:view' },
  { path: '/executions', label: '任务执行', icon: Document, permission: 'execution:view' },
  { path: '/reports/process', label: '项目过程报表', icon: DataAnalysis, permission: 'process_report:view' },
  { path: '/data-exchange', label: '数据导入导出', icon: UploadFilled, permission: 'export:download' },
  { path: '/operation-logs', label: '操作日志', icon: Document, permission: 'operation_log:view' },
].filter(
  (item) => userStore.hasPermission(item.permission),
))

const activePath = computed(() => {
  if (route.path.startsWith('/projects/')) return '/projects'
  return route.path
})
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-mark">协</div>
      <div>
        <strong>项目协同</strong>
        <span>V2.0</span>
      </div>
    </div>
    <el-menu :default-active="activePath" router class="menu">
      <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
        <el-icon><component :is="item.icon" /></el-icon>
        <span>{{ item.label }}</span>
      </el-menu-item>
    </el-menu>
    <div class="sidebar-foot">Project Workforce</div>
  </aside>
</template>

<style scoped>
.sidebar { position: fixed; inset: 0 auto 0 0; z-index: 20; display: flex; width: 232px; flex-direction: column; border-right: 1px solid #e8ebef; background: rgba(255,255,255,.94); backdrop-filter: blur(18px); }
.brand { display: flex; align-items: center; gap: 12px; height: 78px; padding: 0 22px; }
.brand-mark { display: grid; width: 36px; height: 36px; place-items: center; border-radius: 11px; background: #355f8d; color: white; font-weight: 700; box-shadow: 0 6px 15px rgba(53,95,141,.2); }
.brand strong { display: block; color: #172033; font-size: 15px; }
.brand span { color: #a0a8b5; font-size: 11px; }
.menu { flex: 1; overflow-y: auto; border-right: 0; padding: 8px 12px; }
.el-menu-item { height: 45px; margin-bottom: 4px; border-radius: 10px; color: #657083; }
.el-menu-item.is-active { background: #edf3f9; color: #315f8e; font-weight: 600; }
.sidebar-foot { padding: 20px 24px; color: #b0b7c1; font-size: 11px; letter-spacing: .06em; text-transform: uppercase; }
</style>
