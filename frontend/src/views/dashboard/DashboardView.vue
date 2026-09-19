<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Calendar, Collection, Timer, TrendCharts } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getDashboardSummary } from '@/api/report'
import { approveProject, approveProjectHourRequest, getPendingProjectApprovals, getPendingProjectHourRequests, rejectProject, rejectProjectHourRequest } from '@/api/project'
import { getMyTasks } from '@/api/task'
import { confirmSchedule, getMyPendingSchedules, rejectSchedule } from '@/api/schedule'
import type { DashboardSummary } from '@/types/report'
import type { Schedule } from '@/types/schedule'
import type { Project } from '@/types/project'
import type { ProjectHourRequest } from '@/types/project'
import type { Task } from '@/types/task'
import { formatDate, formatDateTime } from '@/utils/format'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const memberOnly = computed(() => {
  const roles = userStore.profile?.roles || []
  return roles.length === 1 && roles[0] === 'project_member'
})
const loading = ref(false)
const decisionState = ref<{ id: number; action: 'approve' | 'reject' }>()
const pendingBookings = ref<Schedule[]>([])
const pendingProjectApprovals = ref<Project[]>([])
const pendingHourRequests = ref<ProjectHourRequest[]>([])
const myTasks = ref<Task[]>([])
const data = ref<DashboardSummary>({
  projects_total: 0, projects_running: 0, projects_completed: 0, projects_delayed: 0,
  delayed_tasks: 0, pending_schedules: 0, pending_project_approvals: 0,
  my_today_tasks: 0, my_upcoming_tasks: 0, today_schedules: 0, open_risks: 0,
  critical_risks: 0, today_risks: 0, weekly_planned_hours: 0, monthly_planned_hours: 0,
  recent_14_day_planned_hours: 0, weekly_utilization_rate: 0,
  recent_14_day_utilization_rate: 0, task_completion_rate: 0, schedule_trend: [],
  planned_hours_scope: '', planned_hours_description: '',
})
const cards = computed(() => {
  if (data.value.pending_project_approvals) return [
    { value: data.value.pending_project_approvals, label: '待审批项目', note: '进入下方审批待办处理', icon: Calendar, color: '#92713c' },
    { value: data.value.projects_running, label: '进行中项目', note: `共 ${data.value.projects_total} 个可见项目`, icon: Collection, color: '#315f8e' },
    { value: data.value.my_today_tasks, label: '今日任务', note: '首页直接查看我的任务', icon: Collection, color: '#a75858' },
    { value: data.value.pending_schedules, label: '待我确认预约', note: `今日 ${data.value.today_schedules} 条安排`, icon: Calendar, color: '#4b7b6b' },
  ]
  if (memberOnly.value) return [
    { value: data.value.my_today_tasks, label: '今日任务', note: '查看今日需要处理的任务', icon: Collection, color: '#315f8e' },
    { value: data.value.my_upcoming_tasks, label: '7 天内到期', note: '关注即将到期的任务', icon: TrendCharts, color: '#4b7b6b' },
    { value: data.value.pending_schedules, label: '待我确认预约', note: `今日 ${data.value.today_schedules} 条安排`, icon: Calendar, color: '#92713c' },
    { value: `${data.value.task_completion_rate}%`, label: '任务完成率', note: `${data.value.delayed_tasks} 个延期任务`, icon: TrendCharts, color: '#6f7790' },
  ]
  return [
    { value: data.value.projects_running, label: '进行中项目', note: `共 ${data.value.projects_total} 个可见项目`, icon: Collection, color: '#315f8e' },
    { value: `${data.value.task_completion_rate}%`, label: '任务完成率', note: `${data.value.delayed_tasks} 个延期任务`, icon: TrendCharts, color: '#4b7b6b' },
    { value: data.value.pending_schedules, label: '待我确认预约', note: `今日 ${data.value.today_schedules} 条安排`, icon: Calendar, color: '#92713c' },
    { value: data.value.my_today_tasks, label: '今日任务', note: `${data.value.my_upcoming_tasks} 个任务将在 7 天内到期`, icon: Collection, color: '#a75858' },
  ]
})
const maxHours = computed(() => Math.max(...data.value.schedule_trend.map(item => item.planned_hours), 1))

async function loadDashboard() {
  loading.value = true
  try {
    const [summary, pending, projects, hours, tasks] = await Promise.all([
      getDashboardSummary(),
      getMyPendingSchedules(8),
      getPendingProjectApprovals(),
      getPendingProjectHourRequests(),
      getMyTasks({ page: 1, page_size: 10 }),
    ])
    data.value = summary
    pendingBookings.value = pending
    pendingProjectApprovals.value = projects
    pendingHourRequests.value = hours
    myTasks.value = tasks.items
  } finally {
    loading.value = false
  }
}

async function approveHours(item: ProjectHourRequest) {
  await ElMessageBox.confirm(`确认批准项目“${item.project_name}”追加 ${item.requested_hours} 小时吗？`, 'L3 工时审批', { type: 'warning' })
  await approveProjectHourRequest(item.project_id, item.id)
  ElMessage.success('追加工时已批准')
  await loadDashboard()
}

async function rejectHours(item: ProjectHourRequest) {
  const { value } = await ElMessageBox.prompt('请输入驳回原因', 'L3 工时审批', { inputType: 'textarea', inputValidator: (text) => Boolean(text?.trim()) || '请填写驳回原因' })
  await rejectProjectHourRequest(item.project_id, item.id, value)
  ElMessage.success('追加工时申请已驳回')
  await loadDashboard()
}

async function approvePendingProject(item: Project) {
  await ElMessageBox.confirm(`确认批准项目“${item.name}”吗？`, '项目审批', { type: 'warning' })
  await approveProject(item.id)
  ElMessage.success('项目已批准')
  await loadDashboard()
}

async function rejectPendingProject(item: Project) {
  const { value } = await ElMessageBox.prompt('请输入驳回原因', '项目审批', { inputType: 'textarea', inputValidator: (text) => Boolean(text?.trim()) || '请填写驳回原因' })
  await rejectProject(item.id, value)
  ElMessage.success('项目已驳回')
  await loadDashboard()
}

async function approveBooking(item: Schedule) {
  try {
    await ElMessageBox.confirm(
      `确认接受 ${dayjs(item.start_time).format('MM月DD日 HH:mm')} 至 ${dayjs(item.end_time).format('HH:mm')} 的预约吗？`,
      '确认人力预约',
      { type: 'success', confirmButtonText: '确认接受' },
    )
  } catch {
    return
  }
  decisionState.value = { id: item.id, action: 'approve' }
  try {
    await confirmSchedule(item.id)
    ElMessage.success('预约已确认')
    await loadDashboard()
  } finally {
    decisionState.value = undefined
  }
}

async function declineBooking(item: Schedule) {
  let reason = ''
  try {
    const result = await ElMessageBox.prompt('请填写拒绝原因，项目经理将收到通知。', '拒绝人力预约', {
      inputPattern: /\S+/,
      inputErrorMessage: '拒绝原因不能为空',
      confirmButtonText: '确认拒绝',
      cancelButtonText: '取消',
      type: 'warning',
    })
    reason = result.value.trim()
  } catch {
    return
  }
  decisionState.value = { id: item.id, action: 'reject' }
  try {
    await rejectSchedule(item.id, reason)
    ElMessage.success('预约已拒绝')
    await loadDashboard()
  } finally {
    decisionState.value = undefined
  }
}

onMounted(loadDashboard)
</script>

<template>
  <div class="page-shell" v-loading="loading">
    <header class="page-header">
      <div><h1 class="page-title">管理驾驶舱</h1><p class="page-subtitle">{{ userStore.profile?.name }}，这里汇总我的任务、项目进度和人力排期。</p></div>
      <div class="header-actions"><el-button type="primary" @click="$router.push('/schedules')">共享看板</el-button></div>
    </header>
    <section class="metrics">
      <article v-for="card in cards" :key="card.label" class="surface metric">
        <div class="metric-icon" :style="{ color: card.color, backgroundColor: `${card.color}14` }"><el-icon><component :is="card.icon" /></el-icon></div>
        <div><span>{{ card.label }}</span><strong>{{ card.value }}</strong><small>{{ card.note }}</small></div>
      </article>
    </section>
    <section class="surface decision-card">
      <div class="decision-header"><div><span class="overline">MY TASKS</span><h2>我的任务</h2><p>首页直接展示由你负责的任务。</p></div><el-button text type="primary" @click="$router.push('/tasks')">查看全部任务</el-button></div>
      <el-empty v-if="!myTasks.length" :image-size="54" description="当前没有由你负责的任务" />
      <el-table v-else :data="myTasks" size="small" class="dashboard-table"><el-table-column prop="name" label="任务" min-width="180"/><el-table-column prop="project_name" label="项目" min-width="150"/><el-table-column prop="owner_name" label="负责人" min-width="120"/><el-table-column label="计划结束" width="130"><template #default="{row}">{{ formatDate(row.planned_end) }}</template></el-table-column><el-table-column prop="effective_status" label="状态" width="100"/></el-table>
    </section>
    <section v-if="pendingHourRequests.length" class="surface decision-card">
      <div class="decision-header"><div><span class="overline">HOUR APPROVALS</span><h2>L3 待审批追加工时</h2><p>批准后工时立即计入项目额度。</p></div></div>
      <div class="decision-list"><article v-for="item in pendingHourRequests" :key="item.id" class="decision-item"><div class="decision-info"><strong>{{ item.project_code }} · {{ item.project_name }}</strong><span>{{ item.requester_name }} 申请追加 {{ item.requested_hours }}h · {{ item.reason }}</span></div><div class="decision-actions"><el-button @click="rejectHours(item)">驳回</el-button><el-button type="success" @click="approveHours(item)">批准</el-button></div></article></div>
    </section>
    <section v-if="pendingProjectApprovals.length" class="surface decision-card">
      <div class="decision-header">
        <div><span class="overline">PROJECT APPROVALS</span><h2>待我审批的项目</h2><p>L3 和超级管理员可处理全部待审批项目，其他审批人仅处理分配给自己的项目。</p></div>
      </div>
      <div class="decision-list">
        <article v-for="item in pendingProjectApprovals.slice(0,8)" :key="item.id" class="decision-item">
          <div class="decision-info"><strong>{{ item.name }}</strong><span>{{ item.code }} · 申请人 {{ item.creator_name || item.manager_name }}</span></div>
          <el-tag type="warning" effect="plain">待审批</el-tag><div class="decision-actions"><el-button @click="rejectPendingProject(item)">驳回</el-button><el-button type="success" @click="approvePendingProject(item)">批准</el-button></div>
        </article>
      </div>
    </section>
    <section class="surface decision-card">
      <div class="decision-header">
        <div>
          <span class="overline">MY APPROVALS</span>
          <h2>待我确认的人力预约</h2>
          <p>这里只展示预约到你本人的待办，可以直接接受或拒绝。</p>
        </div>
        <el-button text type="primary" @click="$router.push('/schedules')">进入共享看板</el-button>
      </div>
      <el-empty v-if="!pendingBookings.length" :image-size="54" description="当前没有需要你确认的预约" />
      <div v-else class="decision-list">
        <article v-for="item in pendingBookings" :key="item.id" class="decision-item">
          <div class="decision-date">
            <strong>{{ dayjs(item.start_time).format('MM/DD') }}</strong>
            <span>{{ dayjs(item.start_time).format('HH:mm') }}–{{ dayjs(item.end_time).format('HH:mm') }}</span>
          </div>
          <div class="decision-info">
            <strong>{{ item.project_name }}</strong>
            <span>{{ item.task_name }} · {{ item.planned_hours }}h{{ item.created_by_name ? ` · 来自 ${item.created_by_name}` : '' }}</span>
          </div>
          <el-tag v-if="item.status==='changed'" type="warning" effect="plain">时间有变更</el-tag>
          <el-tag v-else type="info" effect="plain">新预约</el-tag>
          <div class="decision-actions">
            <el-button :disabled="decisionState!==undefined" :loading="decisionState?.id===item.id&&decisionState?.action==='reject'" @click="declineBooking(item)">拒绝</el-button>
            <el-button type="success" :disabled="decisionState!==undefined" :loading="decisionState?.id===item.id&&decisionState?.action==='approve'" @click="approveBooking(item)">确认预约</el-button>
          </div>
        </article>
      </div>
    </section>
    <section v-if="!memberOnly" class="dashboard-grid">
      <article class="surface trend-card">
        <div class="section-title"><div><span class="overline">WORKFORCE TREND</span><h2>近 14 天计划工时</h2><p class="scope-note">{{ data.planned_hours_scope }}</p></div><div class="week-total" :title="data.planned_hours_description"><el-icon><Timer /></el-icon> 近 14 天 {{ data.recent_14_day_planned_hours }}h · 利用率 {{ data.recent_14_day_utilization_rate }}%</div></div>
        <div class="trend-chart">
          <div v-for="item in data.schedule_trend" :key="item.date" class="trend-column" :title="`${item.date}：${item.planned_hours}h`">
            <span class="bar-value">{{ item.planned_hours || '' }}</span>
            <div class="bar" :style="{ height: `${Math.max(item.planned_hours / maxHours * 120, item.planned_hours ? 5 : 1)}px` }"></div>
            <small>{{ dayjs(item.date).format('MM/DD') }}</small>
          </div>
        </div>
        <p class="metric-help">{{ data.planned_hours_description }}</p>
      </article>
      <article class="surface health-card">
        <span class="overline">PROJECT HEALTH</span><h2>项目健康概览</h2>
        <div class="health-row"><span>已完成项目</span><strong>{{ data.projects_completed }}</strong></div>
        <div class="health-row danger"><span>延期项目</span><strong>{{ data.projects_delayed }}</strong></div>
        <div class="health-row"><span>进行中项目</span><strong>{{ data.projects_running }}</strong></div>
        <div class="health-row"><span>本月计划工时</span><strong>{{ data.monthly_planned_hours }}h</strong></div>
        <el-progress :percentage="data.task_completion_rate" :stroke-width="8" color="#4b7b6b" />
        <p>任务完成率按当前账号的数据范围计算。</p>
      </article>
    </section>
  </div>
</template>

<style scoped>
.header-actions{display:flex;gap:10px}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}.metric{display:flex;align-items:center;gap:15px;padding:20px}.metric-icon{display:grid;width:44px;height:44px;place-items:center;border-radius:13px;font-size:20px}.metric span,.metric small{display:block;color:#8993a1;font-size:11px}.metric strong{display:block;margin:3px 0;color:#202b3d;font-size:26px;font-weight:650}.dashboard-grid{display:grid;grid-template-columns:1.7fr 1fr;gap:16px}.trend-card,.health-card{padding:24px}.section-title{display:flex;align-items:start;justify-content:space-between}.overline{color:#7890aa;font-size:10px;font-weight:700;letter-spacing:.16em}.section-title h2,.health-card h2{margin:8px 0 0;color:#26364a;font-size:17px}.week-total{display:flex;align-items:center;gap:6px;border-radius:9px;background:#f3f6f9;padding:8px 11px;color:#64758a;font-size:12px}.trend-chart{display:flex;height:178px;align-items:end;gap:9px;margin-top:18px;border-bottom:1px solid #e9edf1}.trend-column{display:flex;min-width:0;flex:1;flex-direction:column;align-items:center}.bar-value{height:17px;color:#8792a2;font-size:9px}.bar{width:70%;max-width:28px;border-radius:5px 5px 0 0;background:linear-gradient(#6e91b5,#b7cadb)}.trend-column small{padding:8px 0;color:#9aa3af;font-size:9px;white-space:nowrap}.health-card h2{margin-bottom:18px}.health-row{display:flex;justify-content:space-between;border-bottom:1px solid #f0f2f4;padding:12px 0;color:#667386;font-size:13px}.health-row strong{color:#26364a}.health-row.danger strong{color:#b45252}.health-card .el-progress{margin-top:20px}.health-card p{margin:9px 0 0;color:#98a1ad;font-size:11px;line-height:1.6}
.decision-card{padding:20px 22px}.decision-header{display:flex;align-items:flex-start;justify-content:space-between}.decision-header h2{margin:7px 0 0;color:#26364a;font-size:17px}.decision-header p{margin:6px 0 0;color:#929baa;font-size:11px}.decision-card :deep(.el-empty){padding:15px 0 4px}.decision-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:17px}.decision-item{display:flex;min-width:0;align-items:center;gap:12px;border:1px solid #e8edf1;border-radius:11px;background:#fbfcfd;padding:12px}.decision-date{display:flex;width:78px;flex:0 0 78px;flex-direction:column;border-right:1px solid #e7eaee}.decision-date strong{color:#334a61;font-size:14px}.decision-date span,.decision-info span{margin-top:3px;color:#8994a3;font-size:10px}.decision-info{display:flex;min-width:0;flex:1;flex-direction:column}.decision-info strong,.decision-info span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.decision-info strong{color:#3d4c5f;font-size:12px}.decision-actions{display:flex;flex:0 0 auto;gap:6px}.decision-actions .el-button+.el-button{margin-left:0}
.scope-note{margin:5px 0 0;color:#929baa;font-size:10px}
.metric-help{margin:12px 0 0;color:#8d98a6;font-size:10px;line-height:1.6}
</style>
