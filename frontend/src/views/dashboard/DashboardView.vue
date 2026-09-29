<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { approveProject, approveProjectResourceRequest, rejectProject, rejectProjectResourceRequest } from '@/api/project'
import { confirmSchedule, rejectSchedule } from '@/api/schedule'
import { approveOvertime, rejectOvertime } from '@/api/overtime'
import { getDashboardWorkbench } from '@/api/report'
import DashboardOverviewStats from '@/components/dashboard/DashboardOverviewStats.vue'
import DashboardPendingPanel from '@/components/dashboard/DashboardPendingPanel.vue'
import DashboardMyDay from '@/components/dashboard/DashboardMyDay.vue'
import DashboardProjectTimeline from '@/components/dashboard/DashboardProjectTimeline.vue'
import DashboardTaskExecutionCompare from '@/components/dashboard/DashboardTaskExecutionCompare.vue'
import DashboardRiskAlerts from '@/components/dashboard/DashboardRiskAlerts.vue'
import DashboardWorkhourTrend from '@/components/dashboard/DashboardWorkhourTrend.vue'
import DashboardProjectHealth from '@/components/dashboard/DashboardProjectHealth.vue'
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
const pendingDrawerVisible = ref(false)
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
  if (target === 'pending' || target === 'risks') {
    document.getElementById(`dashboard-${target}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
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
  const confirmation = item.type === 'booking'
    ? `确认接受“${item.title}”的时间预约吗？`
    : `确认批准“${item.title}”吗？`
  try {
    await ElMessageBox.confirm(confirmation, item.type_label, { type: 'warning', confirmButtonText: '确认' })
  } catch {
    return
  }
  actionLoading.value = true
  try {
    if (item.type === 'project_approval') await approveProject(item.source_id)
    else if (item.type === 'resource_approval') await approveProjectResourceRequest(item.project_id, item.source_id)
    else if (item.type === 'overtime_approval') await approveOvertime(item.source_id)
    else await confirmSchedule(item.source_id)
    ElMessage.success(item.type === 'booking' ? '预约已确认' : '审批已通过')
    pendingDrawerVisible.value = false
    await loadDashboard()
  } finally {
    actionLoading.value = false
  }
}

async function rejectPendingItem(item: DashboardPendingItem) {
  let reason = ''
  try {
    const result = await ElMessageBox.prompt('请填写驳回原因，相关人员将收到通知。', `驳回${item.type_label}`, {
      inputType: 'textarea',
      inputPattern: /\S+/,
      inputErrorMessage: '驳回原因不能为空',
      confirmButtonText: '确认驳回',
      cancelButtonText: '取消',
      type: 'warning',
    })
    reason = result.value.trim()
  } catch {
    return
  }
  actionLoading.value = true
  try {
    if (item.type === 'project_approval') await rejectProject(item.source_id, reason)
    else if (item.type === 'resource_approval') await rejectProjectResourceRequest(item.project_id, item.source_id, reason)
    else if (item.type === 'overtime_approval') await rejectOvertime(item.source_id, reason)
    else await rejectSchedule(item.source_id, reason)
    ElMessage.success(item.type === 'booking' ? '预约已拒绝' : '申请已驳回')
    pendingDrawerVisible.value = false
    await loadDashboard()
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

      <section class="workday-grid" aria-label="待办、今日日程与关注事项">
        <DashboardPendingPanel id="dashboard-pending" :overview="dashboard.overview" :pending-items="dashboard.pending_items" :tasks="dashboard.my_tasks" @pending="openPending" @task="openTask" />
        <DashboardMyDay :day="dashboard.my_day" :loading="loading" :failed="loadError" @refresh="loadDashboard" />
        <DashboardRiskAlerts id="dashboard-risks" :items="dashboard.risk_alerts" @select="openRisk" />
      </section>

      <section class="project-grid" aria-label="项目健康度与项目进度">
        <DashboardProjectHealth :items="dashboard.project_health" @project="openProject" />
        <DashboardProjectTimeline :projects="dashboard.timeline" @task="openTask" @project="openProject" />
      </section>

      <section class="analysis-grid" aria-label="计划与实际、工时趋势">
        <DashboardTaskExecutionCompare :items="dashboard.execution_comparison" @task="openTask" />
        <DashboardWorkhourTrend :items="dashboard.workhour_trend" />
      </section>
    </template>

    <section v-else-if="loadError" class="surface dashboard-state"><h2>首页数据暂时无法加载</h2><p>请求已安全结束，不会影响其他页面使用。</p><el-button type="primary" plain @click="loadDashboard">重新加载</el-button></section>
    <section v-else class="dashboard-skeleton" v-loading="loading"><div v-for="index in 8" :key="index" class="surface skeleton-card"></div></section>

    <TaskDetailDrawer v-model="taskDrawerVisible" :task="selectedTask" @open-executions="openExecutions" />
    <PendingDetailDrawer v-model="pendingDrawerVisible" :item="selectedPending" :loading="actionLoading" @approve="approvePending" @reject="rejectPendingItem" @open-project="openProject" />
    <RiskDetailDrawer v-model="riskDrawerVisible" :item="selectedRisk" @open-project="openProject" @open-task="openRiskTask" />
  </div>
</template>

<style scoped>
.dashboard-page { min-width: 0; gap: 24px; font-size: 14px; line-height: 1.6; }
.dashboard-page :deep(.surface) { border-color: #e1e7ed; border-radius: 16px; box-shadow: 0 4px 18px rgba(38,53,70,.035); }
.workday-grid,.project-grid,.analysis-grid { display: grid; gap: 24px; align-items: stretch; }
.workday-grid { grid-template-columns: repeat(3,minmax(0,1fr)); grid-auto-rows: 420px; }
.project-grid { grid-template-columns: minmax(0,1fr) minmax(0,3fr); }
.analysis-grid { grid-template-columns: repeat(2,minmax(0,1fr)); }
.workday-grid > *,.project-grid > *,.analysis-grid > * { min-width: 0; min-height: 0; box-sizing: border-box; }
/* Grid stretches the two cards to one shared, content-sized row. Only the
   lists scroll after the cap; no project records are removed to fit it. */
.project-grid > * { max-height: 640px; }
.analysis-grid > * { max-height: 500px; }
#dashboard-pending,#dashboard-risks { scroll-margin-top: 90px; }
.dashboard-state { display: flex; min-height: 280px; flex-direction: column; align-items: center; justify-content: center; }
.dashboard-state h2 { margin: 0; color: #344256; font-size: 20px; }
.dashboard-state p { margin: 12px 0 20px; color: #718095; font-size: 14px; }
.dashboard-skeleton { display: grid; min-height: 640px; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 24px; }
.skeleton-card { min-height: 116px; background: #f8fafc; }
.skeleton-card:nth-child(5) { grid-column: 1/-1; min-height: 280px; }
.skeleton-card:nth-child(n+6) { grid-column: span 2; min-height: 200px; }
@media(max-width:1440px) {
  .dashboard-page { gap: 20px; }
  .workday-grid,.project-grid,.analysis-grid { gap: 20px; }
}
@media(max-width:1280px) {
  .workday-grid { grid-template-columns: repeat(2,minmax(0,1fr)); }
  .workday-grid > :last-child { grid-column: 1/-1; }
  .project-grid,.analysis-grid { grid-template-columns: minmax(0,1fr); }
  .dashboard-skeleton { grid-template-columns: repeat(2,minmax(0,1fr)); gap: 20px; }
}
</style>
