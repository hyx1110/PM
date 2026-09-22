<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  approveProjectResourceRequest,
  createProjectResourceRequest,
  completeProject,
  getProject,
  getProjectResourceRequests,
  getProjectMembers,
  rejectProjectResourceRequest,
} from '@/api/project'
import { getAllTasks } from '@/api/task'
import { getAllSchedules } from '@/api/schedule'
import { getUserOptions } from '@/api/user'
import { getDepartmentOptions, getOrganizationTree } from '@/api/organization'
import type { DepartmentOption, OrganizationNode } from '@/types/organization'
import type { Project, ProjectMember, ProjectResourceRequest } from '@/types/project'
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
const resourceRequests = ref<ProjectResourceRequest[]>([])
const users = ref<UserOption[]>([])
const departments = ref<DepartmentOption[]>([])
const organizations = ref<OrganizationNode[]>([])
const activeTab = ref('basic')
const resourceDialog = ref(false)
const resourceForm = reactive({
  requested_hours: 0,
  add_member_ids: [] as number[],
  remove_member_ids: [] as number[],
  reason: '',
})
const approvalLabel = { draft: '草稿', pending: '待部门主管审批', approved: '已通过', rejected: '已驳回' }
const resourceStatusLabel = { pending: '待部门主管审批', approved: '已批准', rejected: '已驳回' }
const projectStatusLabel: Record<string, string> = { not_started: '未开始', running: '进行中', completed: '已完成', delayed: '已逾期' }
interface MemberCascaderOption { value: string | number; label: string; children?: MemberCascaderOption[] }
const memberCascaderProps = { multiple: true, emitPath: false }
function organizationMemberOption(node: OrganizationNode): MemberCascaderOption | undefined {
  if (node.status !== 'active') return undefined
  const childOrganizations = (node.children || []).map(organizationMemberOption).filter((item): item is MemberCascaderOption => Boolean(item))
  const existingIds = new Set(members.value.map((item) => item.user_id))
  const userOptions = users.value
    .filter((item) => item.organization_id === node.id && !existingIds.has(item.id))
    .map((item) => ({ value: item.id, label: `${item.name} (${item.employee_no})` }))
  const children = [...childOrganizations, ...userOptions]
  return children.length ? { value: `organization-${node.id}`, label: node.name, children } : undefined
}
const memberCascaderOptions = computed<MemberCascaderOption[]>(() => {
  const existingIds = new Set(members.value.map((item) => item.user_id))
  return departments.value.map((department) => {
    const organizationChildren = organizations.value
      .filter((node) => node.department_id === department.id)
      .map(organizationMemberOption)
      .filter((item): item is MemberCascaderOption => Boolean(item))
    const unassignedMembers = users.value
      .filter((item) => item.department_id === department.id && !item.organization_id && !existingIds.has(item.id))
      .map((item) => ({ value: item.id, label: `${item.name} (${item.employee_no})` }))
    return { value: `department-${department.id}`, label: department.name, children: [...organizationChildren, ...unassignedMembers] }
  }).filter((item) => item.children.length)
})
const removableMembers = computed(() => members.value.filter((item) => item.user_id !== project.value?.manager_id))
const canManageProject = computed(() => {
  if (!project.value || !userStore.hasPermission('project:edit')) return false
  return project.value.can_manage
})
const canModifyProject = computed(
  () => canManageProject.value && project.value?.status !== 'completed',
)
const canRequestResources = computed(
  () =>
    project.value?.approval_status === 'approved'
    && project.value?.status !== 'completed'
    && canManageProject.value,
)
const canReviewResources = (item: ProjectResourceRequest) =>
  item.status === 'pending'
  && (
    userStore.profile?.roles.includes('super_admin')
    || (
      userStore.profile?.roles.includes('department_manager')
      && project.value?.department_manager_id === userStore.profile?.id
    )
  )

async function load() {
  loading.value = true
  try {
    const [p, m, t, s] = await Promise.all([
      getProject(projectId.value),
      getProjectMembers(projectId.value),
      getAllTasks({ project_id: projectId.value }),
      getAllSchedules({ project_id: projectId.value }),
    ])
    project.value = p
    members.value = m
    tasks.value = t
    schedules.value = s
    if (canManageProject.value) {
      const [h, u, d, o] = await Promise.all([
        getProjectResourceRequests(projectId.value),
        getUserOptions(),
        getDepartmentOptions(),
        getOrganizationTree(),
      ])
      resourceRequests.value = h
      users.value = u
      departments.value = d
      organizations.value = o
    } else {
      resourceRequests.value = []
      users.value = []
      departments.value = []
      organizations.value = []
    }
  } finally {
    loading.value = false
  }
}

function openResourceRequest() {
  Object.assign(resourceForm, { requested_hours: 0, add_member_ids: [], remove_member_ids: [], reason: '' })
  resourceDialog.value = true
}

async function submitResourceRequest() {
  if (resourceForm.requested_hours <= 0 && !resourceForm.add_member_ids.length && !resourceForm.remove_member_ids.length) {
    return ElMessage.warning('请至少申请一项工时或成员变更')
  }
  if (!resourceForm.reason.trim()) return ElMessage.warning('请填写申请原因')
  await createProjectResourceRequest(projectId.value, { ...resourceForm, reason: resourceForm.reason.trim() })
  ElMessage.success('项目资源申请已提交部门主管审批')
  resourceDialog.value = false
  await load()
}

const resourceSummary = (item: ProjectResourceRequest) => [
  item.requested_hours > 0 ? `${item.requested_hours}h 工时` : '',
  item.add_member_ids.length ? `新增 ${item.add_member_ids.length} 人` : '',
  item.remove_member_ids.length ? `移除 ${item.remove_member_ids.length} 人` : '',
].filter(Boolean).join('、')

async function approveResources(item: ProjectResourceRequest) {
  await ElMessageBox.confirm(
    `确认批准资源申请（${resourceSummary(item)}）吗？`,
    '部门主管资源审批',
    { type: 'warning' },
  )
  await approveProjectResourceRequest(projectId.value, item.id)
  ElMessage.success('项目资源申请已批准')
  await load()
}

async function rejectResources(item: ProjectResourceRequest) {
  const { value } = await ElMessageBox.prompt('请输入驳回原因', '部门主管资源审批', {
    inputType: 'textarea',
    inputValidator: (value) => Boolean(value?.trim()) || '请填写驳回原因',
  })
  await rejectProjectResourceRequest(projectId.value, item.id, value)
  ElMessage.success('项目资源申请已驳回')
  await load()
}

async function finishProject() {
  await ElMessageBox.confirm('全部任务已完成，是否正式确认项目完成？确认前仍可补充或调整任务，确认后项目停止新增任务。', '确认项目完成', { type: 'warning', confirmButtonText: '确认完成' })
  await completeProject(projectId.value)
  ElMessage.success('项目已正式完成')
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
        <p class="page-subtitle">{{ project?.code }} · {{ project?.manager_name }} · {{ project ? (projectStatusLabel[project.effective_status] || project.effective_status) : '' }}</p>
      </div>
      <el-button v-if="canRequestResources" type="primary" @click="openResourceRequest">项目资源申请</el-button>
    </header>
    <el-alert v-if="project?.all_tasks_completed && canModifyProject && project.approval_status==='approved'" type="success" :closable="false" show-icon title="当前项目全部任务已完成，项目尚未关闭。">
      <template #default>可以继续补充或调整任务；全部工作结束后，请 <el-button link type="success" @click="finishProject">确认项目完成</el-button>。</template>
    </el-alert>
    <el-alert
      v-if="project && project.approval_status!=='approved'"
      :title="project.approval_status==='draft' ? '项目尚未提交审批，审批前不能添加成员、任务或预约人力。' : project.approval_status==='pending' ? `项目正在等待 ${project.approval_required_name || '所属部门主管'} 审批。` : `项目已被驳回：${project.approval_note || '未填写原因'}`"
      :type="project.approval_status==='draft' ? 'info' : project.approval_status==='pending' ? 'warning' : 'error'"
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
            <el-descriptions-item label="状态">{{ projectStatusLabel[project.effective_status] || project.effective_status }}</el-descriptions-item>
            <el-descriptions-item label="项目经理">{{ project.manager_name }}</el-descriptions-item>
            <el-descriptions-item label="所属部门">{{ project.department_name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="计划周期">{{ formatDate(project.planned_start) }} 至 {{ formatDate(project.planned_end) }}</el-descriptions-item>
            <el-descriptions-item label="实际周期">{{ formatDate(project.actual_start) }} 至 {{ formatDate(project.actual_end) }}</el-descriptions-item>
            <el-descriptions-item label="审批人">{{ project.approver_name || project.approval_required_name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="审批时间">{{ formatDateTime(project.approved_at) }}</el-descriptions-item>
            <el-descriptions-item label="审批意见" :span="3">{{ project.approval_note || '—' }}</el-descriptions-item>
            <el-descriptions-item label="描述" :span="3">{{ project.description || '—' }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>
        <el-tab-pane name="members">
          <template #label>项目成员 <el-badge :value="members.length" type="info" /></template>
          <div class="tab-tools">
            <span>仅展示当前有效成员；成员增删统一通过“项目资源申请”并由部门主管审批</span>
            <el-button v-if="canRequestResources" type="primary" size="small" @click="openResourceRequest">申请成员变更</el-button>
          </div>
          <el-table :data="members">
            <el-table-column prop="user_name" label="成员"/>
            <el-table-column label="项目角色"><template #default="{row}">{{ row.project_role === 'manager' ? '项目经理' : row.project_role }}</template></el-table-column>
            <el-table-column label="加入时间"><template #default="{row}">{{ formatDate(row.joined_at) }}</template></el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane :label="`项目任务 (${tasks.length})`" name="tasks">
          <div class="tab-tools"><span>项目下多级任务</span><el-button size="small" @click="router.push('/tasks')">进入任务管理</el-button></div>
          <el-table :data="tasks">
            <el-table-column prop="name" label="任务" min-width="180"/>
            <el-table-column prop="owner_name" label="项目成员"/>
            <el-table-column label="计划日期" width="220"><template #default="{row}">{{ formatDate(row.planned_start) }} 至 {{ formatDate(row.planned_end) }}</template></el-table-column>
            <el-table-column prop="effective_status" label="状态"/>
          </el-table>
        </el-tab-pane>
        <el-tab-pane :label="`人力预约 (${schedules.length})`" name="schedules">
          <div class="tab-tools"><span>预约经成员确认后才占用项目额度</span><el-button size="small" @click="router.push('/schedules')">进入共享看板</el-button></div>
          <el-table :data="schedules">
            <el-table-column prop="user_name" label="人员"/>
            <el-table-column prop="task_name" label="任务" min-width="180"/>
            <el-table-column label="预约时间" width="290"><template #default="{row}">{{ formatDateTime(row.start_time) }} 至 {{ formatDateTime(row.end_time) }}</template></el-table-column>
            <el-table-column prop="planned_hours" label="工时"/>
            <el-table-column prop="status" label="状态"/>
          </el-table>
        </el-tab-pane>
        <el-tab-pane v-if="canManageProject" :label="`资源申请 (${resourceRequests.length})`" name="resources">
          <div class="tab-tools"><span>工时与项目成员变更都必须由项目所属部门主管审批</span><el-button v-if="canRequestResources" size="small" type="primary" @click="openResourceRequest">发起申请</el-button></div>
          <el-table :data="resourceRequests">
            <el-table-column prop="requester_name" label="申请人" width="110"/>
            <el-table-column label="资源变更" min-width="170"><template #default="{row}">{{ resourceSummary(row) }}</template></el-table-column>
            <el-table-column prop="reason" label="申请原因" min-width="180"/>
            <el-table-column label="状态" width="115"><template #default="{row}">{{ resourceStatusLabel[row.status] }}</template></el-table-column>
            <el-table-column prop="reviewer_name" label="审批人" width="110"/>
            <el-table-column prop="review_note" label="审批意见" min-width="150"/>
            <el-table-column label="申请时间" width="160"><template #default="{row}">{{ formatDateTime(row.created_at) }}</template></el-table-column>
            <el-table-column label="操作" width="130"><template #default="{row}"><el-button v-if="canReviewResources(row)" link type="success" @click="approveResources(row)">批准</el-button><el-button v-if="canReviewResources(row)" link type="danger" @click="rejectResources(row)">驳回</el-button></template></el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </section>

    <el-dialog v-model="resourceDialog" title="项目资源申请" width="620px">
      <el-form :model="resourceForm" label-position="top">
        <el-alert title="追加工时、添加成员和移除成员统一提交，部门主管批准后才生效。" type="info" :closable="false" show-icon/>
        <el-form-item label="追加工时（可选）"><el-input-number v-model="resourceForm.requested_hours" :min="0" :step="0.5" :precision="2" style="width:100%"/></el-form-item>
        <el-form-item label="添加项目成员（可选）">
          <el-cascader v-model="resourceForm.add_member_ids" :options="memberCascaderOptions" :props="memberCascaderProps" clearable collapse-tags collapse-tags-tooltip filterable placeholder="按部门 / 组织选择成员" style="width:100%"/>
        </el-form-item>
        <el-form-item label="移除项目成员（可选）">
          <el-select v-model="resourceForm.remove_member_ids" multiple filterable clearable collapse-tags placeholder="项目经理不可移除" style="width:100%"><el-option v-for="item in removableMembers" :key="item.user_id" :label="item.user_name" :value="item.user_id"/></el-select>
        </el-form-item>
        <el-form-item label="申请原因" required><el-input v-model="resourceForm.reason" type="textarea" :rows="4" maxlength="2000" show-word-limit/></el-form-item>
      </el-form>
      <template #footer><el-button @click="resourceDialog=false">取消</el-button><el-button type="primary" @click="submitResourceRequest">提交部门主管审批</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.detail-title{margin-top:8px}.detail-card{padding:12px 24px 24px}.tab-tools{display:flex;align-items:center;justify-content:space-between;margin:8px 0 16px;color:#8b95a3;font-size:12px}.quota-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.quota{padding:18px}.quota span{display:block;color:#8b95a3;font-size:12px}.quota strong{display:block;margin-top:8px;color:#34445b;font-size:23px}.quota strong.danger{color:#c45656}
</style>
