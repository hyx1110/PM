<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { confirmAction, requestActionReason } from '@/utils/confirm'
import {
  approveProjectResourceRequest,
  createProjectResourceRequest,
  completeProject,
  getProject,
  getProjectResourceRequests,
  getProjectMembers,
  rejectProjectResourceRequest,
  withdrawProjectResourceRequest,
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
import TaskManagementPanel from '@/components/task/TaskManagementPanel.vue'
import dayjs from 'dayjs'
import { usePlannedHours } from '@/composables/usePlannedHours'
import PlannedHoursHint from '@/components/common/PlannedHoursHint.vue'
import ProjectReportField from '@/components/project/ProjectReportField.vue'

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
const activeTab = ref(route.query.tab === 'resources' ? 'resources' : 'basic')
const resourceDialog = ref(false)
const resourceSaving = ref(false)
const resourceActionId = ref<number>()
const resourceForm = reactive({
  requested_hours: 0,
  requested_planned_start: undefined as string | undefined,
  requested_planned_end: undefined as string | undefined,
  add_member_ids: [] as number[],
  remove_member_ids: [] as number[],
  reason: '',
})
const approvalLabel = { draft: '草稿', pending: '待部门主管审批', approved: '已通过', rejected: '已驳回' }
const resourceStatusLabel = { pending: '待部门主管审批', approved: '已批准', rejected: '已驳回', withdrawn: '已撤回' }
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
const effectiveStart = computed(() => resourceForm.requested_planned_start || project.value?.planned_start || '')
const effectiveEnd = computed(() => resourceForm.requested_planned_end || project.value?.planned_end || '')
const changedStart = computed(() => effectiveStart.value !== project.value?.planned_start ? resourceForm.requested_planned_start || null : null)
const changedEnd = computed(() => effectiveEnd.value !== project.value?.planned_end ? resourceForm.requested_planned_end || null : null)
const isEndExtension = computed(() => !!project.value && effectiveEnd.value > project.value.planned_end)
const extensionMembers = computed(() => {
  const ids = new Set(members.value.map(item => item.user_id))
  if (project.value) ids.add(project.value.manager_id)
  resourceForm.add_member_ids.forEach(id => ids.add(id))
  resourceForm.remove_member_ids.forEach(id => ids.delete(id))
  return [...ids]
})
const extensionStart = computed(() => {
  if (!project.value) return ''
  const nextDay = dayjs(project.value.planned_end).add(1, 'day').format('YYYY-MM-DD')
  return effectiveStart.value > nextDay ? effectiveStart.value : nextDay
})
const extensionHours = usePlannedHours({
  enabled: () => resourceDialog.value && canRequestResources.value && isEndExtension.value && effectiveEnd.value >= effectiveStart.value,
  start: () => extensionStart.value,
  end: () => resourceForm.requested_planned_end || '',
  members: () => extensionMembers.value,
  getHours: () => resourceForm.requested_hours,
  setHours: value => { resourceForm.requested_hours = value },
})
const extensionHoursInput = extensionHours.input
watch(isEndExtension, extending => {
  // Clearing/changing the end date must not leave an obsolete automatic increment.
  if (!extending && !extensionHours.manual.value) resourceForm.requested_hours = 0
}, { flush: 'sync' })
const canWithdrawResources = (item: ProjectResourceRequest) => item.status === 'pending' && item.requested_by === userStore.profile?.id
const canReviewResources = (item: ProjectResourceRequest) =>
  item.status === 'pending'
  && userStore.profile?.roles.includes('department_manager')
  && project.value?.department_manager_id === userStore.profile?.id
  && project.value?.department_id === userStore.profile?.department_id

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
  extensionHours.reset()
  Object.assign(resourceForm, { requested_hours: 0, requested_planned_start: undefined, requested_planned_end: undefined, add_member_ids: [], remove_member_ids: [], reason: '' })
  resourceDialog.value = true
}

async function submitResourceRequest() {
  if (resourceSaving.value) return
  if (!canRequestResources.value) return ElMessage.warning('仅已审批且未完成的项目可以申请资源变更')
  if (effectiveEnd.value < effectiveStart.value) return ElMessage.warning('计划结束日期不能早于计划开始日期')
  if (extensionHours.loading.value && !extensionHours.manual.value) return ElMessage.warning('正在计算延期工时，请稍候')
  if (isEndExtension.value && !extensionHours.manual.value && !extensionHours.estimate.value) return ElMessage.warning('尚未取得有效的延期工时计算结果，请重新选择日期或手动填写工时')
  if (!Number.isFinite(resourceForm.requested_hours) || resourceForm.requested_hours < 0 || !Number.isInteger(resourceForm.requested_hours * 2)) return ElMessage.warning('追加工时须为非负数，且以 0.5 小时为单位')
  if (isEndExtension.value && resourceForm.requested_hours <= 0) return ElMessage.warning('延长计划结束日期必须填写正数追加工时')
  if (resourceForm.requested_hours <= 0 && !resourceForm.add_member_ids.length && !resourceForm.remove_member_ids.length && !changedStart.value && !changedEnd.value) {
    return ElMessage.warning('请至少修改一项计划日期、工时或项目成员')
  }
  if (!resourceForm.reason.trim()) return ElMessage.warning('请填写申请原因')
  resourceSaving.value = true
  try {
    if (!(await confirmAction(
      `项目：${project.value?.name}\n追加工时：${resourceForm.requested_hours}h`
      + (changedStart.value ? `\n计划开始：${project.value?.planned_start} → ${changedStart.value}` : '')
      + (changedEnd.value ? `\n计划结束：${project.value?.planned_end} → ${changedEnd.value}` : '')
      + `\n新增成员：${resourceForm.add_member_ids.map(id => users.value.find(user => user.id === id)?.name || `人员 ${id}`).join('、') || '无'}`
      + `\n移除成员：${resourceForm.remove_member_ids.map(id => members.value.find(member => member.user_id === id)?.user_name || `人员 ${id}`).join('、') || '无'}`
      + '\n确认提交资源申请？部门主管批准后才生效。', '提交项目资源申请',
    ))) return
    await createProjectResourceRequest(projectId.value, { ...resourceForm, requested_planned_start: changedStart.value, requested_planned_end: changedEnd.value, reason: resourceForm.reason.trim() })
    ElMessage.success('项目资源申请已提交部门主管审批')
    resourceDialog.value = false
    await load()
  } catch { /* API interceptor displays the error. */ }
  finally { resourceSaving.value = false }
}

const memberNames = (people?: ProjectResourceRequest['add_members']) => people?.map(person => person.employee_no ? `${person.name}（${person.employee_no}）` : person.name).join('、') || '名单暂不可用，请刷新'
const resourceSummary = (item: ProjectResourceRequest) => [
  item.requested_planned_start ? `计划开始 ${formatDate(item.original_planned_start)} → ${formatDate(item.requested_planned_start)}` : '',
  item.requested_planned_end ? `计划结束 ${formatDate(item.original_planned_end)} → ${formatDate(item.requested_planned_end)}` : '',
  item.requested_hours > 0 ? `${item.requested_hours}h 工时` : '',
  item.add_member_ids.length ? `新增 ${item.add_member_ids.length} 人：${memberNames(item.add_members)}` : '',
  item.remove_member_ids.length ? `移除 ${item.remove_member_ids.length} 人：${memberNames(item.remove_members)}` : '',
].filter(Boolean).join('；')

async function withdrawResources(item: ProjectResourceRequest) {
  if (resourceActionId.value) return
  resourceActionId.value = item.id
  try {
    if (!(await confirmAction(`撤回项目资源申请（${resourceSummary(item)}）？撤回后不会变更项目工时、成员或日期，可重新申请。`, '撤回资源申请', '确认撤回'))) return
    await withdrawProjectResourceRequest(projectId.value, item.id)
    ElMessage.success('资源申请已撤回')
    await load()
  } catch { /* Cancellation is expected; API errors are displayed by the interceptor. */ }
  finally { resourceActionId.value = undefined }
}

async function approveResources(item: ProjectResourceRequest) {
  if (resourceActionId.value) return
  resourceActionId.value = item.id
  try {
    if (!(await confirmAction(`确认批准资源申请（${resourceSummary(item)}）吗？`, '部门主管资源审批', '确认批准'))) return
    await approveProjectResourceRequest(projectId.value, item.id)
    ElMessage.success('项目资源申请已批准')
    await load()
  } catch { /* Cancellation is expected; API interceptor displays failures. */ }
  finally { resourceActionId.value = undefined }
}

async function rejectResources(item: ProjectResourceRequest) {
  if (resourceActionId.value) return
  resourceActionId.value = item.id
  try {
    const value = await requestActionReason('驳回资源申请', '请输入驳回原因')
    if (value === null || !(await confirmAction(`项目：${project.value?.name}\n申请：${resourceSummary(item)}\n驳回原因：${value}\n确认驳回？`, '驳回资源申请', '确认驳回'))) return
    await rejectProjectResourceRequest(projectId.value, item.id, value)
    ElMessage.success('项目资源申请已驳回')
    await load()
  } catch { /* Cancellation is expected; API interceptor displays failures. */ }
  finally { resourceActionId.value = undefined }
}

async function finishProject() {
  if (!(await confirmAction('全部任务已完成，是否正式确认项目完成？确认前仍可补充或调整任务，确认后项目停止新增任务。', '确认项目完成', '确认完成'))) return
  await completeProject(projectId.value)
  ElMessage.success('项目已正式完成')
  await load()
}

async function refreshTaskSummary() {
  try {
    const [p, t] = await Promise.all([getProject(projectId.value), getAllTasks({ project_id: projectId.value })])
    project.value = p
    tasks.value = t
  } catch { /* API interceptor displays the error. */ }
}

onMounted(async () => { try { await load() } catch { /* API interceptor displays the error. */ } })
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
      <div class="surface quota"><span>已占用工时（含待确认）</span><strong>{{ project.booked_hours }}h</strong></div>
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
            <el-descriptions-item label="项目立项报告" :span="3"><ProjectReportField :project-id="project.id"/></el-descriptions-item>
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
          <TaskManagementPanel v-if="activeTab==='tasks'" :key="projectId" :project-id="projectId" @changed="refreshTaskSummary"/>
        </el-tab-pane>
        <el-tab-pane :label="`人力预约 (${schedules.length})`" name="schedules">
          <div class="tab-tools"><span>提交即预占任务及项目额度，确认后占用人员时段；拒绝或撤回后释放额度</span><el-button size="small" @click="router.push('/schedules')">进入共享看板</el-button></div>
          <el-table :data="schedules">
            <el-table-column prop="user_name" label="人员"/>
            <el-table-column prop="task_name" label="任务" min-width="180"/>
            <el-table-column label="预约时间" width="290"><template #default="{row}">{{ formatDateTime(row.start_time) }} 至 {{ formatDateTime(row.end_time) }}</template></el-table-column>
            <el-table-column prop="planned_hours" label="工时"/>
            <el-table-column prop="status" label="状态"/>
          </el-table>
        </el-tab-pane>
        <el-tab-pane v-if="canManageProject" :label="`资源申请 (${resourceRequests.length})`" name="resources">
          <div class="tab-tools"><span>计划日期、工时和成员变更均由项目所属部门主管审批后生效</span><el-button v-if="canRequestResources" size="small" type="primary" @click="openResourceRequest">发起申请</el-button></div>
          <el-table :data="resourceRequests">
            <el-table-column prop="requester_name" label="申请人" width="110"/>
            <el-table-column label="资源变更（含成员名单）" min-width="300"><template #default="{row}">{{ resourceSummary(row) }}</template></el-table-column>
            <el-table-column prop="reason" label="申请原因" min-width="180"/>
            <el-table-column label="状态" width="115"><template #default="{row}">{{ resourceStatusLabel[row.status] }}</template></el-table-column>
            <el-table-column prop="reviewer_name" label="审批人" width="110"/>
            <el-table-column prop="review_note" label="审批意见" min-width="150"/>
            <el-table-column label="申请时间" width="160"><template #default="{row}">{{ formatDateTime(row.created_at) }}</template></el-table-column>
            <el-table-column label="操作" width="180"><template #default="{row}"><el-button v-if="canReviewResources(row)" :disabled="!!resourceActionId" link type="success" @click="approveResources(row)">批准</el-button><el-button v-if="canReviewResources(row)" :disabled="!!resourceActionId" link type="danger" @click="rejectResources(row)">驳回</el-button><el-button v-if="canWithdrawResources(row)" :disabled="!!resourceActionId" link type="warning" @click="withdrawResources(row)">撤回</el-button></template></el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </section>

    <el-dialog v-model="resourceDialog" title="项目资源申请" width="620px">
      <el-form :model="resourceForm" label-position="top">
        <el-alert title="计划日期、工时和成员变更统一申请，无需等到项目逾期；部门主管批准后才生效。" type="info" :closable="false" show-icon/>
        <p class="extension-hint">当前计划：{{formatDate(project?.planned_start)}} 至 {{formatDate(project?.planned_end)}}。日期留空表示不变，不自动移动任务或预约；新周期须覆盖已有任务和有效预约。</p>
        <el-form-item label="新计划开始日期（可选）">
          <el-date-picker v-model="resourceForm.requested_planned_start" type="date" value-format="YYYY-MM-DD" clearable placeholder="留空则保持原开始日期" style="width:100%"/>
        </el-form-item>
        <el-form-item label="新计划结束日期（可选）">
          <el-date-picker v-model="resourceForm.requested_planned_end" type="date" value-format="YYYY-MM-DD" clearable placeholder="留空则保持原结束日期" style="width:100%"/>
        </el-form-item>
        <el-form-item :label="isEndExtension ? '追加工时（延长结束日期时必填）' : '追加工时（可选）'" :required="isEndExtension"><el-input-number v-model="extensionHoursInput" :min="0" :step="0.5" step-strictly :precision="1" style="width:100%"/></el-form-item>
        <template v-if="isEndExtension">
          <p class="extension-hint">仅计算延期新增周期：{{extensionStart}} 至 {{resourceForm.requested_planned_end}}，按变更后的有效项目成员人数（含项目经理）计算，不重复计入原项目预算。</p>
          <PlannedHoursHint :estimate="extensionHours.estimate.value" :loading="extensionHours.loading.value" :manual="extensionHours.manual.value" :error="extensionHours.error.value" includes-manager @reset="extensionHours.useDefault"/>
        </template>
        <p v-else class="extension-hint">仅调整开始日期或提前结束日期可保留 0 工时；如需增加预算，可手动填写追加工时。日期缩短不会自动扣减已批工时。</p>
        <el-form-item label="添加项目成员（可选）">
          <el-cascader v-model="resourceForm.add_member_ids" :options="memberCascaderOptions" :props="memberCascaderProps" clearable collapse-tags collapse-tags-tooltip filterable placeholder="按部门 / 组织选择成员" style="width:100%"/>
        </el-form-item>
        <el-form-item label="移除项目成员（可选）">
          <el-select v-model="resourceForm.remove_member_ids" multiple filterable clearable collapse-tags placeholder="项目经理不可移除" style="width:100%"><el-option v-for="item in removableMembers" :key="item.user_id" :label="item.user_name" :value="item.user_id"/></el-select>
        </el-form-item>
        <el-form-item label="申请原因" required><el-input v-model="resourceForm.reason" type="textarea" :rows="4" maxlength="2000" show-word-limit/></el-form-item>
      </el-form>
      <template #footer><el-button :disabled="resourceSaving" @click="resourceDialog=false">取消</el-button><el-button type="primary" :loading="resourceSaving" @click="submitResourceRequest">提交部门主管审批</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.extension-hint{margin-top:6px;color:var(--el-text-color-secondary);font-size:12px;line-height:1.6}
.detail-title{margin-top:8px}.detail-card{padding:12px 24px 24px}.tab-tools{display:flex;align-items:center;justify-content:space-between;margin:8px 0 16px;color:#8b95a3;font-size:12px}.quota-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.quota{padding:18px}.quota span{display:block;color:#8b95a3;font-size:12px}.quota strong{display:block;margin-top:8px;color:#34445b;font-size:23px}.quota strong.danger{color:#c45656}
</style>
