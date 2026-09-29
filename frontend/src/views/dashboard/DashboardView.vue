<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { approveProject, approveProjectResourceRequest, rejectProject, rejectProjectResourceRequest } from '@/api/project'
import { confirmSchedule, rejectSchedule } from '@/api/schedule'
import { approveOvertime, rejectOvertime } from '@/api/overtime'
import { getDashboardWorkbench } from '@/api/report'
import DashboardOverviewStats from '@/components/dashboard/DashboardOverviewStats.vue'
import DashboardProjectTimeline from '@/components/dashboard/DashboardProjectTimeline.vue'
import DashboardTaskExecutionCompare from '@/components/dashboard/DashboardTaskExecutionCompare.vue'
import DashboardRiskAlerts from '@/components/dashboard/DashboardRiskAlerts.vue'
import DashboardWorkhourTrend from '@/components/dashboard/DashboardWorkhourTrend.vue'
import DashboardProjectHealth from '@/components/dashboard/DashboardProjectHealth.vue'
import TaskDetailDrawer from '@/components/dashboard/TaskDetailDrawer.vue'
import PendingDetailDrawer from '@/components/dashboard/PendingDetailDrawer.vue'
import RiskDetailDrawer from '@/components/dashboard/RiskDetailDrawer.vue'
import type { DashboardPendingItem, DashboardRiskAlert, DashboardTaskItem, DashboardWorkbench } from '@/types/report'
import { formatDateTime } from '@/utils/format'
import { useUserStore } from '@/stores/user'

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

async function loadDashboard() {
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

onMounted(() => { void loadDashboard() })
</script>

<template>
  <div class="page-shell dashboard-page">
    <header class="page-header dashboard-header">
      <div class="dashboard-heading"><h1 class="page-title">管理驾驶舱</h1><p class="page-subtitle">{{userStore.profile?.name}}，先看待办与项目进展，再查看执行情况。</p></div>
      <div v-if="dashboard" class="scope-meta"><i></i><div><span>{{dashboard.scope_label}}</span><small>数据更新于 {{formatDateTime(dashboard.generated_at)}}</small></div></div>
    </header>

    <template v-if="dashboard">
      <DashboardOverviewStats :overview="dashboard.overview" :pending-items="dashboard.pending_items" :tasks="dashboard.my_tasks" @open="openOverview" @pending="openPending" @task="openTask" />

      <DashboardProjectTimeline :projects="dashboard.timeline" @task="openTask" @project="openProject" />

      <section class="detail-grid" aria-label="执行对比与关注事项">
        <DashboardTaskExecutionCompare :items="dashboard.execution_comparison" @task="openTask" />
        <div id="dashboard-risks"><DashboardRiskAlerts :items="dashboard.risk_alerts" @select="openRisk" /></div>
      </section>

      <section class="detail-grid" aria-label="工时趋势与项目健康度">
        <DashboardWorkhourTrend :items="dashboard.workhour_trend" />
        <DashboardProjectHealth :items="dashboard.project_health" @project="openProject" />
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
.dashboard-header { align-items: center; padding: 4px 0 2px; }
.dashboard-header .page-title { color: #172235; font-size: 28px; font-weight: 680; letter-spacing: -.025em; }
.dashboard-header .page-subtitle { margin-top: 8px; color: #65758a; font-size: 14px; line-height: 1.6; }
.dashboard-heading { min-width: 0; }
.scope-meta { display: flex; flex-shrink: 0; align-items: center; gap: 12px; padding: 12px 16px; border: 1px solid #e1e7ed; border-radius: 12px; background: rgba(255,255,255,.8); }
.scope-meta > i { width: 8px; height: 8px; border-radius: 50%; background: #4f846f; }
.scope-meta > div { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }
.scope-meta span { color: #4d5d70; font-size: 14px; font-weight: 600; }
.scope-meta small { color: #758397; font-size: 12px; }
.detail-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 24px; align-items: start; }
.detail-grid > * { min-width: 0; }
#dashboard-risks { scroll-margin-top: 90px; }
.dashboard-state { display: flex; min-height: 280px; flex-direction: column; align-items: center; justify-content: center; }
.dashboard-state h2 { margin: 0; color: #344256; font-size: 20px; }
.dashboard-state p { margin: 12px 0 20px; color: #718095; font-size: 14px; }
.dashboard-skeleton { display: grid; min-height: 640px; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 24px; }
.skeleton-card { min-height: 116px; background: #f8fafc; }
.skeleton-card:nth-child(5) { grid-column: 1/-1; min-height: 280px; }
.skeleton-card:nth-child(n+6) { grid-column: span 2; min-height: 200px; }
@media(max-width:1440px) {
  .dashboard-page { gap: 20px; }
  .detail-grid { grid-template-columns: minmax(0,1fr); gap: 20px; }
  .dashboard-header { flex-wrap: wrap; }
}
@media(max-width:1280px) {
  .dashboard-skeleton { grid-template-columns: repeat(2,minmax(0,1fr)); gap: 20px; }
}
</style>
