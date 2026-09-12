<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  addProjectMember,
  approveProjectHourRequest,
  createProjectHourRequest,
  getProject,
  getProjectHourRequests,
  getProjectMembers,
  rejectProjectHourRequest,
  removeProjectMember,
} from '@/api/project'
import { getTasks } from '@/api/task'
import { getSchedules } from '@/api/schedule'
import { getUserOptions } from '@/api/user'
import { getDepartmentOptions } from '@/api/organization'
import type { DepartmentOption } from '@/types/organization'
import type { Project, ProjectHourRequest, ProjectMember } from '@/types/project'
import type { Schedule } from '@/types/schedule'
import type { Task } from '@/types/task'
import type { UserOption } from '@/types/user'
import { formatDate, formatDateTime } from '@/utils/format'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const projectId = computed(() => Number(route.params.id))
const loading = ref(false)
const project = ref<Project>()
const members = ref<ProjectMember[]>([])
const tasks = ref<Task[]>([])
const schedules = ref<Schedule[]>([])
const hourRequests = ref<ProjectHourRequest[]>([])
const users = ref<UserOption[]>([])
const departments = ref<DepartmentOption[]>([])
const activeTab = ref('basic')
const memberDialog = ref(false)
const hourDialog = ref(false)
const memberForm = reactive({
  user_id: undefined as number | undefined,
  project_role: 'member',
  allocation_percent: 100,
  joined_at: '',
})
const hourForm = reactive({ requested_hours: 8, reason: '' })
const approvalLabel = { pending: '待 L3 审批', approved: '已审批', rejected: '已驳回' }
const hourStatusLabel = { pending: '待 L3 审批', approved: '已批准', rejected: '已驳回' }
const canRequestHours = computed(
  () =>
    project.value?.approval_status === 'approved'
    && project.value.manager_id === userStore.profile?.id
    && userStore.profile?.roles.includes('project_manager'),
)
const canReviewHours = (item: ProjectHourRequest) =>
  item.status === 'pending'
  && userStore.profile?.roles.includes('department_manager')
  && project.value?.department_id === userStore.profile?.department_id
  && departments.value.find((department) => department.id === project.value?.department_id)?.manager_id === userStore.profile?.id

async function load() {
  loading.value = true
  try {
    const [p, m, t, s, h, u, d] = await Promise.all([
      getProject(projectId.value),
      getProjectMembers(projectId.value),
      getTasks({ project_id: projectId.value, page: 1, page_size: 200 }),
      getSchedules({ project_id: projectId.value, page: 1, page_size: 200 }),
      getProjectHourRequests(projectId.value),
      getUserOptions(),
      getDepartmentOptions(),
    ])
    project.value = p
    members.value = m
    tasks.value = t.items
    schedules.value = s.items
    hourRequests.value = h
    users.value = u
    departments.value = d
  } finally {
    loading.value = false
  }
}

function openMember() {
  Object.assign(memberForm, {
    user_id: undefined,
    project_role: 'member',
    allocation_percent: 100,
    joined_at: new Date().toISOString().slice(0, 10),
  })
  memberDialog.value = true
}

async function saveMember() {
  if (!memberForm.user_id) return ElMessage.warning('请选择成员')
  await addProjectMember(projectId.value, {
    ...memberForm,
    user_id: memberForm.user_id,
    joined_at: `${memberForm.joined_at} 00:00:00`,
  })
  ElMessage.success('成员已添加')
  memberDialog.value = false
  await load()
}

async function removeMember(row: ProjectMember) {
  await ElMessageBox.confirm(`确认移除成员“${row.user_name}”吗？`, '移除成员', {
    type: 'warning',
  })
  await removeProjectMember(projectId.value, row.user_id)
  ElMessage.success('成员已移除')
  await load()
}

function openHourRequest() {
  hourForm.requested_hours = 8
  hourForm.reason = ''
  hourDialog.value = true
}

async function submitHourRequest() {
  if (hourForm.requested_hours <= 0 || !hourForm.reason.trim()) {
    return ElMessage.warning('请填写追加工时与申请原因')
  }
  await createProjectHourRequest(
    projectId.value,
    hourForm.requested_hours,
    hourForm.reason.trim(),
  )
  ElMessage.success('追加工时申请已提交 L3 审批')
  hourDialog.value = false
  await load()
}

async function approveHours(item: ProjectHourRequest) {
  await ElMessageBox.confirm(
    `确认批准追加 ${item.requested_hours} 小时吗？`,
    'L3 工时审批',
    { type: 'warning' },
  )
  await approveProjectHourRequest(projectId.value, item.id)
  ElMessage.success('追加工时已批准并计入项目额度')
  await load()
}

async function rejectHours(item: ProjectHourRequest) {
  const { value } = await ElMessageBox.prompt('请输入驳回原因', 'L3 工时审批', {
    inputType: 'textarea',
    inputValidator: (value) => Boolean(value?.trim()) || '请填写驳回原因',
  })
  await rejectProjectHourRequest(projectId.value, item.id, value)
  ElMessage.success('追加工时申请已驳回')
  await load()
}

onMounted(load)
</script>

<template>
  <div class="page-shell" v-loading="loading">
    <header class="page-header">
      <div>
        <el-button link @click="router.push('/projects')">← 返回项目列表</el-button>
        <h1 class="page-title detail-title">{{ project?.name || '项目详情' }}</h1>
        <p class="page-subtitle">{{ project?.code }} · {{ project?.manager_name }} · {{ project?.status }}</p>
      </div>
      <el-button v-if="canRequestHours" type="primary" @click="openHourRequest">申请追加工时</el-button>
    </header>
    <el-alert
      v-if="project && project.approval_status!=='approved'"
      :title="project.approval_status==='pending' ? '项目正在等待 L3 审批，审批前不能添加成员、任务或预约人力。' : `项目已被 L3 驳回：${project.approval_note || '未填写原因'}`"
      :type="project.approval_status==='pending' ? 'warning' : 'error'"
      :closable="false"
      show-icon
    />
    <section class="quota-grid" v-if="project">
      <div class="surface quota"><span>项目总工时</span><strong>{{ project.budget_hours }}h</strong></div>
      <div class="surface quota"><span>已预约工时</span><strong>{{ project.booked_hours }}h</strong></div>
      <div class="surface quota"><span>剩余工时</span><strong :class="{ danger: project.remaining_hours<=0 }">{{ project.remaining_hours }}h</strong></div>
      <div class="surface quota"><span>审批状态</span><strong>{{ approvalLabel[project.approval_status] }}</strong></div>
    </section>
    <section class="surface detail-card">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="基本信息" name="basic">
          <el-descriptions v-if="project" :column="3" border>
            <el-descriptions-item label="项目编号">{{ project.code }}</el-descriptions-item>
            <el-descriptions-item label="项目类型">{{ project.project_type }}</el-descriptions-item>
            <el-descriptions-item label="状态">{{ project.status }}</el-descriptions-item>
            <el-descriptions-item label="项目经理">{{ project.manager_name }}</el-descriptions-item>
            <el-descriptions-item label="所属部门">{{ project.department_name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="优先级">{{ project.priority }}</el-descriptions-item>
            <el-descriptions-item label="计划周期">{{ formatDate(project.planned_start) }} 至 {{ formatDate(project.planned_end) }}</el-descriptions-item>
            <el-descriptions-item label="审批人">{{ project.approver_name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="审批时间">{{ formatDateTime(project.approved_at) }}</el-descriptions-item>
            <el-descriptions-item label="审批意见" :span="3">{{ project.approval_note || '—' }}</el-descriptions-item>
            <el-descriptions-item label="描述" :span="3">{{ project.description || '—' }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>
        <el-tab-pane name="members">
          <template #label>项目成员 <el-badge :value="members.length" type="info" /></template>
          <div class="tab-tools">
            <span>仅展示当前有效成员</span>
            <el-button v-if="project?.approval_status==='approved' && userStore.hasPermission('project:edit')" type="primary" size="small" @click="openMember">添加成员</el-button>
          </div>
          <el-table :data="members">
            <el-table-column prop="user_name" label="成员"/>
            <el-table-column prop="project_role" label="项目角色"/>
            <el-table-column prop="allocation_percent" label="投入比例"><template #default="{row}">{{ row.allocation_percent }}%</template></el-table-column>
            <el-table-column label="加入时间"><template #default="{row}">{{ formatDate(row.joined_at) }}</template></el-table-column>
            <el-table-column v-if="project?.approval_status==='approved' && userStore.hasPermission('project:edit')" label="操作" width="90"><template #default="{row}"><el-button link type="danger" @click="removeMember(row)">移除</el-button></template></el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane :label="`项目任务 (${tasks.length})`" name="tasks">
          <div class="tab-tools"><span>项目下一级与二级任务</span><el-button size="small" @click="router.push('/tasks')">进入任务管理</el-button></div>
          <el-table :data="tasks">
            <el-table-column prop="name" label="任务" min-width="180"/>
            <el-table-column prop="task_type" label="类型"/>
            <el-table-column prop="owner_name" label="负责人"/>
            <el-table-column label="计划时间" width="280"><template #default="{row}">{{ formatDateTime(row.planned_start) }} 至 {{ formatDateTime(row.planned_end) }}</template></el-table-column>
            <el-table-column prop="effective_status" label="状态"/>
          </el-table>
        </el-tab-pane>
        <el-tab-pane :label="`人力预约 (${schedules.length})`" name="schedules">
          <div class="tab-tools"><span>预约工时在提交时占用项目额度</span><el-button size="small" @click="router.push('/schedules')">进入共享看板</el-button></div>
          <el-table :data="schedules">
            <el-table-column prop="user_name" label="人员"/>
            <el-table-column prop="task_name" label="任务" min-width="180"/>
            <el-table-column label="预约时间" width="290"><template #default="{row}">{{ formatDateTime(row.start_time) }} 至 {{ formatDateTime(row.end_time) }}</template></el-table-column>
            <el-table-column prop="planned_hours" label="工时"/>
            <el-table-column prop="status" label="状态"/>
          </el-table>
        </el-tab-pane>
        <el-tab-pane :label="`工时申请 (${hourRequests.length})`" name="hours">
          <div class="tab-tools"><span>追加额度必须由项目所属部门当前 L3 审批</span><el-button v-if="canRequestHours" size="small" type="primary" @click="openHourRequest">申请追加</el-button></div>
          <el-table :data="hourRequests">
            <el-table-column prop="requester_name" label="申请人" width="110"/>
            <el-table-column prop="requested_hours" label="追加工时" width="100"/>
            <el-table-column prop="reason" label="申请原因" min-width="180"/>
            <el-table-column label="状态" width="115"><template #default="{row}">{{ hourStatusLabel[row.status] }}</template></el-table-column>
            <el-table-column prop="reviewer_name" label="审批人" width="110"/>
            <el-table-column prop="review_note" label="审批意见" min-width="150"/>
            <el-table-column label="申请时间" width="160"><template #default="{row}">{{ formatDateTime(row.created_at) }}</template></el-table-column>
            <el-table-column label="操作" width="130"><template #default="{row}"><el-button v-if="canReviewHours(row)" link type="success" @click="approveHours(row)">批准</el-button><el-button v-if="canReviewHours(row)" link type="danger" @click="rejectHours(row)">驳回</el-button></template></el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </section>

    <el-dialog v-model="memberDialog" title="添加项目成员" width="500px">
      <el-form :model="memberForm" label-position="top">
        <el-form-item label="成员"><el-select v-model="memberForm.user_id" filterable style="width:100%"><el-option v-for="item in users.filter(u=>!members.some(m=>m.user_id===u.id))" :key="item.id" :label="`${item.name} (${item.username})`" :value="item.id"/></el-select></el-form-item>
        <el-form-item label="项目角色"><el-input v-model="memberForm.project_role"/></el-form-item>
        <el-form-item label="投入比例"><el-input-number v-model="memberForm.allocation_percent" :min="0" :max="100" style="width:100%"/></el-form-item>
        <el-form-item label="加入日期"><el-date-picker v-model="memberForm.joined_at" value-format="YYYY-MM-DD" style="width:100%"/></el-form-item>
      </el-form>
      <template #footer><el-button @click="memberDialog=false">取消</el-button><el-button type="primary" @click="saveMember">添加</el-button></template>
    </el-dialog>
    <el-dialog v-model="hourDialog" title="申请追加项目工时" width="500px">
      <el-form :model="hourForm" label-position="top">
        <el-form-item label="追加工时" required><el-input-number v-model="hourForm.requested_hours" :min="0.5" :step="0.5" :precision="2" style="width:100%"/></el-form-item>
        <el-form-item label="申请原因" required><el-input v-model="hourForm.reason" type="textarea" :rows="4" maxlength="2000" show-word-limit/></el-form-item>
      </el-form>
      <template #footer><el-button @click="hourDialog=false">取消</el-button><el-button type="primary" @click="submitHourRequest">提交 L3 审批</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.detail-title{margin-top:8px}.detail-card{padding:12px 24px 24px}.tab-tools{display:flex;align-items:center;justify-content:space-between;margin:8px 0 16px;color:#8b95a3;font-size:12px}.quota-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.quota{padding:18px}.quota span{display:block;color:#8b95a3;font-size:12px}.quota strong{display:block;margin-top:8px;color:#34445b;font-size:23px}.quota strong.danger{color:#c45656}
</style>
