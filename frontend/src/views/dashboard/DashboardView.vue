<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { approveProject, approveProjectResourceRequest, rejectProject, rejectProjectResourceRequest } from '@/api/project'
import { confirmSchedule, rejectSchedule } from '@/api/schedule'
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
      <div class="dashboard-heading"><span class="page-kicker">WORKSPACE OVERVIEW</span><h1 class="page-title">管理驾驶舱</h1><p class="page-subtitle">{{userStore.profile?.name}}，这里汇总你权限范围内的项目进度、任务执行和待处理事项。</p></div>
      <div v-if="dashboard" class="scope-meta"><i></i><div><span>{{dashboard.scope_label}}</span><small>数据更新于 {{formatDateTime(dashboard.generated_at)}}</small></div></div>
    </header>

    <template v-if="dashboard">
      <DashboardOverviewStats :overview="dashboard.overview" :pending-items="dashboard.pending_items" :tasks="dashboard.my_tasks" @open="openOverview" @pending="openPending" @task="openTask" />

      <section class="progress-grid">
        <DashboardProjectTimeline :projects="dashboard.timeline" @task="openTask" @project="openProject" />
        <DashboardTaskExecutionCompare :items="dashboard.execution_comparison" @task="openTask" />
      </section>

      <section class="analysis-grid">
        <DashboardWorkhourTrend :items="dashboard.workhour_trend" />
        <DashboardProjectHealth :items="dashboard.project_health" @project="openProject" />
        <div id="dashboard-risks"><DashboardRiskAlerts :items="dashboard.risk_alerts" @select="openRisk" /></div>
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
.dashboard-page{gap:16px}.dashboard-page :deep(.surface){border-color:#e1e7ed;border-radius:15px;box-shadow:0 10px 30px rgba(38,53,70,.055)}.dashboard-header{align-items:flex-end;padding:2px 1px 0}.dashboard-header .page-title{color:#172235;font-size:25px;font-weight:680;letter-spacing:-.025em}.dashboard-header .page-subtitle{margin-top:7px;color:#728094;font-size:12px}.dashboard-heading{min-width:0}.page-kicker{display:block;margin-bottom:6px;color:#6c88a4;font-size:9px;font-weight:750;letter-spacing:.16em}.scope-meta{display:flex;align-items:center;gap:10px;border:1px solid #e1e7ed;border-radius:12px;background:rgba(255,255,255,.76);padding:9px 12px;box-shadow:0 5px 18px rgba(45,61,80,.035)}.scope-meta>i{width:7px;height:7px;border-radius:50%;background:#4f846f;box-shadow:0 0 0 4px #edf6f2}.scope-meta>div{display:flex;flex-direction:column;align-items:flex-end}.scope-meta span{color:#4d5d70;font-size:11px;font-weight:650}.scope-meta small{margin-top:3px;color:#939eab;font-size:9px}.progress-grid{display:grid;grid-template-columns:minmax(0,1.72fr) minmax(315px,.7fr);gap:16px;align-items:stretch}.progress-grid>*{height:100%}.analysis-grid{display:grid;grid-template-columns:minmax(0,1.36fr) minmax(280px,.72fr) minmax(280px,.72fr);gap:16px;align-items:stretch}.analysis-grid>div,.analysis-grid>*{min-width:0;height:100%}.dashboard-state{display:flex;min-height:280px;flex-direction:column;align-items:center;justify-content:center}.dashboard-state h2{margin:0;color:#344256;font-size:17px}.dashboard-state p{margin:8px 0 18px;color:#8b96a4;font-size:11px}.dashboard-skeleton{display:grid;min-height:520px;grid-template-columns:repeat(4,1fr);gap:16px}.skeleton-card{min-height:110px;background:linear-gradient(100deg,#fff 20%,#f7f9fb 50%,#fff 80%);background-size:240% 100%;animation:skeleton 1.6s ease infinite}.skeleton-card:nth-child(n+5){grid-column:span 2;min-height:180px}@keyframes skeleton{to{background-position:-240% 0}}@media(max-width:1500px){.progress-grid{grid-template-columns:minmax(0,1.45fr) minmax(300px,.7fr)}.analysis-grid{grid-template-columns:1fr 1fr}.analysis-grid>:first-child{grid-column:1/-1}}@media(max-width:1180px){.progress-grid,.analysis-grid{grid-template-columns:1fr}.analysis-grid>:first-child{grid-column:auto}.dashboard-skeleton{grid-template-columns:repeat(2,1fr)}}
</style>
