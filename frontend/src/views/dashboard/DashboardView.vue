<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { confirmAction, requestActionReason } from '@/utils/confirm'
import { approveProject, approveProjectResourceRequest, rejectProject, rejectProjectResourceRequest } from '@/api/project'
import { confirmSchedule, rejectSchedule } from '@/api/schedule'
import { approveOvertime, rejectOvertime } from '@/api/overtime'
import { approveTask, rejectTask } from '@/api/task'
import { getDashboardWorkbench } from '@/api/report'
import DashboardOverviewStats from '@/components/dashboard/DashboardOverviewStats.vue'
import DashboardPendingDrawer from '@/components/dashboard/DashboardPendingDrawer.vue'
import DashboardMyDay from '@/components/dashboard/DashboardMyDay.vue'
import DashboardProjectTimeline from '@/components/dashboard/DashboardProjectTimeline.vue'
import DashboardRiskAlerts from '@/components/dashboard/DashboardRiskAlerts.vue'
import TaskDetailDrawer from '@/components/dashboard/TaskDetailDrawer.vue'
import PendingDetailDrawer from '@/components/dashboard/PendingDetailDrawer.vue'
import RiskDetailDrawer from '@/components/dashboard/RiskDetailDrawer.vue'
import type { DashboardPendingItem, DashboardRiskAlert, DashboardTaskItem, DashboardWorkbench } from '@/types/report'
import { useUserStore } from '@/stores/user'
import { beijingNow } from '@/utils/time'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const actionLoading = ref(false)
const loadError = ref(false)
const dashboard = ref<DashboardWorkbench>()
const selectedTask = ref<DashboardTaskItem>()
const selectedPending = ref<DashboardPendingItem>()
const selectedRisk = ref<DashboardRiskAlert>()
const taskDrawerVisible = ref(false)
const pendingListDrawerVisible = ref(false)
const pendingDrawerVisible = ref(false)
const riskListDrawerVisible = ref(false)
const riskDrawerVisible = ref(false)
let dayRefreshTimer: ReturnType<typeof setInterval> | undefined
let lastAttemptDay = ''

async function loadDashboard() {
  if (loading.value) return
  lastAttemptDay = beijingNow().format('YYYY-MM-DD')
  loading.value = true
  loadError.value = false
  try {
    dashboard.value = await getDashboardWorkbench()
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

function openOverview(target: 'projects' | 'tasks' | 'pending' | 'risks') {
  if (target === 'pending') {
    pendingListDrawerVisible.value = true
    return
  }
  if (target === 'risks') {
    riskListDrawerVisible.value = true
    return
  }
  router.push(target === 'projects' ? '/projects' : '/tasks')
}

function openTask(item: DashboardTaskItem) {
  selectedTask.value = item
  taskDrawerVisible.value = true
}

function openPending(item: DashboardPendingItem) {
  selectedPending.value = item
  pendingDrawerVisible.value = true
}

function openRisk(item: DashboardRiskAlert) {
  selectedRisk.value = item
  riskDrawerVisible.value = true
}

function openProject(id: number) {
  router.push(`/projects/${id}`)
}

function openExecutions(item: DashboardTaskItem) {
  if (!userStore.hasPermission('execution:view')) {
    ElMessage.info('当前账号没有查看任务执行记录的权限')
    return
  }
  router.push({ path: '/executions', query: { project_id: item.project_id, task_id: item.id } })
}

function openRiskTask(taskId: number) {
  const candidates = [
    ...(dashboard.value?.my_tasks || []),
    ...(dashboard.value?.execution_comparison || []),
    ...(dashboard.value?.timeline.flatMap(project => project.tasks) || []),
  ]
  const task = candidates.find(item => item.id === taskId)
  if (task) openTask(task)
  else router.push('/tasks')
}

async function approvePending(item: DashboardPendingItem) {
  if (actionLoading.value) return
  const confirmation = item.type === 'booking'
    ? `确认接受“${item.title}”的时间预约吗？`
    : `确认批准“${item.title}”吗？`
  if (!(await confirmAction(`${confirmation}\n关联项目：${item.project_name}\n${item.content}`, item.type_label, item.type === 'booking' ? '确认接受预约' : '确认批准'))) return
  actionLoading.value = true
  try {
    if (item.type === 'project_approval') await approveProject(item.source_id)
    else if (item.type === 'resource_approval') await approveProjectResourceRequest(item.project_id, item.source_id)
    else if (item.type === 'overtime_approval') await approveOvertime(item.source_id)
    else if (item.type === 'task_approval') await approveTask(item.source_id)
    else await confirmSchedule(item.source_id)
    ElMessage.success(item.type === 'booking' ? '预约已确认' : '审批已通过')
    pendingDrawerVisible.value = false
    await loadDashboard()
  } catch {
    // The API interceptor shows stale-state and permission errors; keep details open.
  } finally {
    actionLoading.value = false
  }
}

async function rejectPendingItem(item: DashboardPendingItem) {
  if (actionLoading.value) return
  const reason = await requestActionReason(`驳回${item.type_label}`, '请填写驳回原因，相关人员将收到通知。')
  if (reason === null || !(await confirmAction(`事项：${item.title}\n关联项目：${item.project_name}\n驳回原因：${reason}\n确认驳回并通知相关人员？`, `驳回${item.type_label}`, '确认驳回'))) return
  actionLoading.value = true
  try {
    if (item.type === 'project_approval') await rejectProject(item.source_id, reason)
    else if (item.type === 'resource_approval') await rejectProjectResourceRequest(item.project_id, item.source_id, reason)
    else if (item.type === 'overtime_approval') await rejectOvertime(item.source_id, reason)
    else if (item.type === 'task_approval') await rejectTask(item.source_id, reason)
    else await rejectSchedule(item.source_id, reason)
    ElMessage.success(item.type === 'booking' ? '预约已拒绝' : '申请已驳回')
    pendingDrawerVisible.value = false
    await loadDashboard()
  } catch {
    // The API interceptor shows stale-state and permission errors; keep details open.
  } finally {
    actionLoading.value = false
  }
}

function refreshOnNewDay() {
  // Refresh after Beijing midnight, including returning to a suspended tab.
  // Once per new day: failed requests remain explicitly retryable, not a loop.
  if (document.visibilityState === 'visible' && lastAttemptDay !== beijingNow().format('YYYY-MM-DD')) void loadDashboard()
}
onMounted(() => {
  void loadDashboard()
  dayRefreshTimer = setInterval(refreshOnNewDay, 60000)
  document.addEventListener('visibilitychange', refreshOnNewDay)
})
onUnmounted(() => {
  if (dayRefreshTimer) clearInterval(dayRefreshTimer)
  document.removeEventListener('visibilitychange', refreshOnNewDay)
})
</script>

<template>
  <div class="page-shell dashboard-page">
    <template v-if="dashboard">
      <DashboardOverviewStats :overview="dashboard.overview" @open="openOverview" />

      <section class="project-grid" aria-label="我的今日日程与项目进度">
        <DashboardMyDay :day="dashboard.my_day" :loading="loading" :failed="loadError" @refresh="loadDashboard" @pending="openOverview('pending')" />
        <DashboardProjectTimeline :projects="dashboard.timeline" @task="openTask" @project="openProject" />
      </section>
    </template>

    <section v-else-if="loadError" class="surface dashboard-state"><h2>首页数据暂时无法加载</h2><p>请求已安全结束，不会影响其他页面使用。</p><el-button type="primary" plain @click="loadDashboard">重新加载</el-button></section>
    <section v-else class="dashboard-skeleton" v-loading="loading"><div v-for="index in 6" :key="index" class="surface skeleton-card"></div></section>

    <DashboardPendingDrawer
      v-if="dashboard" v-model="pendingListDrawerVisible" :overview="dashboard.overview"
      :pending-items="dashboard.pending_items" :tasks="dashboard.my_tasks" :loading="loading" :failed="loadError"
      @pending="openPending" @task="openTask" @refresh="loadDashboard"
    />
    <el-drawer v-model="riskListDrawerVisible" title="需要关注" direction="rtl" size="min(640px, 100vw)" append-to-body destroy-on-close>
      <div v-if="dashboard" class="risk-drawer-body">
        <DashboardRiskAlerts class="drawer-list" embedded :items="dashboard.risk_alerts" @select="openRisk" />
      </div>
      <template #footer><el-button @click="riskListDrawerVisible=false">关闭</el-button></template>
    </el-drawer>
    <TaskDetailDrawer v-model="taskDrawerVisible" :task="selectedTask" @open-executions="openExecutions" />
    <PendingDetailDrawer v-model="pendingDrawerVisible" :item="selectedPending" :loading="actionLoading" @approve="approvePending" @reject="rejectPendingItem" @open-project="openProject" />
    <RiskDetailDrawer v-model="riskDrawerVisible" :item="selectedRisk" @open-project="openProject" @open-task="openRiskTask" />
  </div>
</template>

<style scoped>
.dashboard-page {
  --dashboard-grid-columns: 4;
  --dashboard-grid-gap: 20px;
  --dashboard-day-span: 1;
  --dashboard-project-span: 3;
  min-width: 0; gap: 24px; font-size: 14px; line-height: 1.6;
}
.dashboard-page :deep(.surface) { border-color: #e1e7ed; border-radius: 16px; box-shadow: 0 4px 18px rgba(38,53,70,.035); }
/* Match the overview's four tracks, including gaps: a 1fr/3fr two-column grid
   does not line up with a four-column grid because it subtracts fewer gaps. */
.project-grid { display: grid; grid-template-columns: repeat(var(--dashboard-grid-columns),minmax(0,1fr)); gap: var(--dashboard-grid-gap); align-items: stretch; }
.project-grid > * { min-width: 0; box-sizing: border-box; }
.project-grid > :first-child { grid-column: span var(--dashboard-day-span); }
.project-grid > :last-child { grid-column: span var(--dashboard-project-span); }
/* Grid stretches the two cards to one shared, content-sized row. Only the
   lists scroll after the cap; no project records are removed to fit it. */
.project-grid > * { min-height: 320px; max-height: 640px; }
.risk-drawer-body { display: flex; height: 100%; min-height: 0; flex-direction: column; }
.drawer-list { min-height: 0; flex: 1; }
.dashboard-state { display: flex; min-height: 280px; flex-direction: column; align-items: center; justify-content: center; }
.dashboard-state h2 { margin: 0; color: #344256; font-size: 20px; }
.dashboard-state p { margin: 12px 0 20px; color: #718095; font-size: 14px; }
.dashboard-skeleton { display: grid; grid-template-columns: repeat(var(--dashboard-grid-columns),minmax(0,1fr)); gap: var(--dashboard-grid-gap); }
.skeleton-card { min-height: 132px; background: #f8fafc; }
.skeleton-card:nth-child(n+5) { min-height: 360px; }
.skeleton-card:nth-child(5) { grid-column: span var(--dashboard-day-span); }
.skeleton-card:nth-child(6) { grid-column: span var(--dashboard-project-span); }
@media(max-width:1500px) {
  .dashboard-page { --dashboard-grid-columns: 2; --dashboard-project-span: 1; }
}
@media(max-width:1440px) {
  .dashboard-page { gap: 20px; }
}
@media(max-width:1280px) {
  .dashboard-page { --dashboard-day-span: 2; --dashboard-project-span: 2; }
}
</style>
