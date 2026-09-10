import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes: RouteRecordRaw[] = [
  { path: '/login', name: 'login', component: () => import('@/views/auth/LoginView.vue'), meta: { title: '登录', public: true } },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', component: () => import('@/views/dashboard/DashboardView.vue'), meta: { title: '首页' } },
      { path: 'users', component: () => import('@/views/user/UserView.vue'), meta: { title: '用户管理', permission: 'user:view' } },
      { path: 'organizations', component: () => import('@/views/organization/OrganizationView.vue'), meta: { title: '组织管理', permission: 'organization:view' } },
      { path: 'roles', component: () => import('@/views/role/RoleView.vue'), meta: { title: '角色权限', permission: 'role:view' } },
      { path: 'projects', component: () => import('@/views/project/ProjectView.vue'), meta: { title: '项目管理', permission: 'project:view' } },
      { path: 'projects/:id', component: () => import('@/views/project/ProjectDetailView.vue'), meta: { title: '项目详情', permission: 'project:view' } },
      { path: 'tasks', component: () => import('@/views/task/TaskView.vue'), meta: { title: '任务管理', permission: 'task:view' } },
      { path: 'schedules', component: () => import('@/views/schedule/ScheduleBoardView.vue'), meta: { title: '任务共享看板', permission: 'schedule:view' } },
      { path: 'executions', component: () => import('@/views/execution/ExecutionView.vue'), meta: { title: '任务执行', permission: 'execution:view' } },
      { path: 'reports/process', component: () => import('@/views/report/ProcessReportView.vue'), meta: { title: '项目过程报表', permission: 'process_report:view' } },
      { path: 'operation-logs', component: () => import('@/views/operation-log/OperationLogView.vue'), meta: { title: '操作日志', permission: 'operation_log:view' } },
      { path: '403', component: () => import('@/views/error/ForbiddenView.vue'), meta: { title: '无权限' } },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  document.title = `${to.meta.title || '系统'} - ${import.meta.env.VITE_APP_TITLE || '项目协同管理'}`
  if (to.meta.public) return true
  const userStore = useUserStore()
  if (!userStore.token) return { path: '/login', query: { redirect: to.fullPath } }
  if (!userStore.loaded) {
    try {
      await userStore.fetchProfile()
    } catch {
      await userStore.logout()
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  }
  if (!userStore.hasPermission(to.meta.permission)) return '/403'
  return true
})

export default router

