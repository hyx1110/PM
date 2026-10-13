<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { confirmAction } from '@/utils/confirm'
import { ArrowDown, ArrowRight } from '@element-plus/icons-vue'
import { approveTask, createTask, deleteTask, getAllTasks, getTask, getTasks, rejectTask, submitTask, updateTask } from '@/api/task'
import { getAllProjects, getProject, getProjectMembers } from '@/api/project'
import { getUserOptions } from '@/api/user'
import { getDepartmentOptions, getOrganizationTree } from '@/api/organization'
import type { DepartmentOption, OrganizationNode } from '@/types/organization'
import type { Project } from '@/types/project'
import type { Task, TaskPayload } from '@/types/task'
import type { UserOption } from '@/types/user'
import { formatDate } from '@/utils/format'
import { useUserStore } from '@/stores/user'
import PersonnelScopeCascader from '@/components/common/PersonnelScopeCascader.vue'
import PlannedHoursHint from '@/components/common/PlannedHoursHint.vue'
import { usePlannedHours } from '@/composables/usePlannedHours'
import { isPositiveHalfHour } from '@/utils/hours'

const props = defineProps<{ projectId?: number }>()
const emit = defineEmits<{ changed: [] }>()
const userStore = useUserStore()
const router = useRouter()
const loading = ref(false)
const tasks = ref<Task[]>([])
const projectTasks = ref<Task[]>([])
const total = ref(0)
const projects = ref<Project[]>([])
const users = ref<UserOption[]>([])
const departments = ref<DepartmentOption[]>([])
const organizations = ref<OrganizationNode[]>([])
const filterScopes = ref<string[]>([])
const projectMemberOptions = ref<UserOption[]>([])
const query = reactive({
  page: 1, page_size: 100, project_id: props.projectId as number | undefined,
  status: '', approval_status: '',
})
const dialogVisible = ref(false)
const saving = ref(false)
const editingId = ref<number>()
const editingTextOnly = ref(false)
const editingProjectName = ref('')
const reviewTask = ref<Task>()
const reviewVisible = ref(false)
const reviewNote = ref('')
const reviewBusy = ref(false)
const submittingId = ref<number>()
const formRef = ref<FormInstance>()
const emptyForm = (): TaskPayload => ({
  project_id: 0, parent_id: undefined, name: '', owner_ids: [],
  planned_start: '', planned_end: '', estimated_hours: 0.5,
  description: '', remark: '',
})
const form = reactive<TaskPayload>(emptyForm())
const { input: hoursInput, estimate: hoursEstimate, loading: hoursLoading, manual: hoursManual,
  error: hoursError, reset: resetHours, useDefault: useDefaultHours } = usePlannedHours({
  enabled: () => dialogVisible.value && !editingId.value,
  start: () => form.planned_start, end: () => form.planned_end, members: () => form.owner_ids,
  getHours: () => form.estimated_hours, setHours: value => { form.estimated_hours = value },
})
const rules: FormRules = {
  project_id: [{ required: true, message: '请选择项目' }],
  name: [{ required: true, message: '请输入任务名称' }],
  owner_ids: [{ required: true, type: 'array', min: 1, message: '请至少选择一名项目成员' }],
  planned_start: [{ required: true, message: '请选择计划开始日期' }],
  planned_end: [{ required: true, message: '请选择计划结束日期' }],
  estimated_hours: [{ required: true, message: '请输入任务计划工时' }],
}
const filterStatuses = ['not_started', 'running', 'completed', 'delayed']
const statusLabel: Record<string, string> = { not_started: '未开始', running: '进行中', completed: '已完成', delayed: '已逾期' }
const approvalLabels: Record<string, string> = { pending: '待部门主管审批', approved: '已通过', rejected: '已驳回', not_required: '子任务免审批' }
const isExecutable = (task: Task) => ['approved', 'not_required'].includes(task.approval_status)
const canManageProject = (project?: Project) => Boolean(project?.can_manage)
const canExecuteTask = (task: Task) => isExecutable(task) && (task.owner_ids.includes(userStore.profile?.id || -1)
  || task.project_manager_id === userStore.profile?.id
  || Boolean(userStore.profile?.roles.some(role => ['super_admin', 'department_manager'].includes(role))))
const manageableProjects = computed(() => projects.value.filter(canManageProject))
const approvedProjects = computed(() => manageableProjects.value.filter((item) => item.approval_status === 'approved' && item.status !== 'completed'))
const selectedProject = computed(() => projects.value.find((item) => item.id === form.project_id))
const allocatedProjectHours = computed(() => projectTasks.value
  .filter((item) => item.project_id === form.project_id && !item.parent_id && item.id !== editingId.value)
  .reduce((total, item) => total + Number(item.estimated_hours), 0))
const selectedParent = computed(() => projectTasks.value.find((item) => item.id === form.parent_id))
const remainingParentHours = computed(() => selectedParent.value
  ? Number(selectedParent.value.estimated_hours) - projectTasks.value
    .filter(item => item.parent_id === selectedParent.value?.id && item.id !== editingId.value)
    .reduce((hours, item) => hours + Number(item.estimated_hours), 0)
  : 0)
const descendantIds = computed(() => {
  const ids = new Set<number>()
  if (!editingId.value) return ids
  const visit = (parentId: number) => projectTasks.value
    .filter((item) => item.parent_id === parentId)
    .forEach((item) => { ids.add(item.id); visit(item.id) })
  visit(editingId.value)
  return ids
})
const parentOptions = computed(() => projectTasks.value.filter(
  (item) =>
    item.id !== editingId.value
    && !descendantIds.value.has(item.id)
    && isExecutable(item),
))
const ownerOptions = computed(() => {
  if (!selectedParent.value) return projectMemberOptions.value
  const allowed = new Set(selectedParent.value.owner_ids)
  return projectMemberOptions.value.filter((item) => allowed.has(item.id))
})
interface TaskNode { row: Task; children: TaskNode[] }
type TaskTreeRow = Task & { treeLevel: number; hasChildren: boolean }
const expandedTaskIds = ref<Set<number>>(new Set())
const taskForest = computed<TaskNode[]>(() => {
  const nodes = new Map<number, TaskNode>()
  const rootsByProject = new Map<number, TaskNode[]>()
  const projectOrder: number[] = []
  tasks.value.forEach((item) => nodes.set(item.id, { row: item, children: [] }))
  tasks.value.forEach((item) => {
    const node = nodes.get(item.id)!
    const parent = item.parent_id ? nodes.get(item.parent_id) : undefined
    if (parent && parent.row.project_id === item.project_id) {
      parent.children.push(node)
      return
    }
    if (!rootsByProject.has(item.project_id)) {
      rootsByProject.set(item.project_id, [])
      projectOrder.push(item.project_id)
    }
    rootsByProject.get(item.project_id)!.push(node)
  })
  return projectOrder.flatMap((projectId) => rootsByProject.get(projectId) || [])
})
const visibleTaskRows = computed<TaskTreeRow[]>(() => {
  const rows: TaskTreeRow[] = []
  const visit = (node: TaskNode, level: number) => {
    rows.push({ ...node.row, treeLevel: level, hasChildren: node.children.length > 0 })
    if (node.children.length && expandedTaskIds.value.has(node.row.id)) {
      node.children.forEach((child) => visit(child, level + 1))
    }
  }
  taskForest.value.forEach((node) => visit(node, 0))
  return rows
})
const projectRowSpans = computed(() => {
  const spans = new Map<number, number>()
  for (let index = 0; index < visibleTaskRows.value.length;) {
    let count = 1
    while (visibleTaskRows.value[index + count]?.project_id === visibleTaskRows.value[index].project_id) count += 1
    spans.set(index, count)
    for (let offset = 1; offset < count; offset += 1) spans.set(index + offset, 0)
    index += count
  }
  return spans
})
function resetExpandedTasks() {
  expandedTaskIds.value = new Set(tasks.value.map((item) => item.parent_id).filter((id): id is number => Boolean(id)))
}
function toggleTask(row: TaskTreeRow) {
  const next = new Set(expandedTaskIds.value)
  if (next.has(row.id)) next.delete(row.id)
  else next.add(row.id)
  expandedTaskIds.value = next
}
function taskSpanMethod({ rowIndex, column }: { rowIndex: number; column: { property?: string } }) {
  if (column.property !== 'project_name') return [1, 1]
  const span = projectRowSpans.value.get(rowIndex) ?? 1
  return span ? [span, 1] : [0, 0]
}
async function load() {
  loading.value = true
  try {
    const result = await getTasks({
      ...query,
      project_id: props.projectId ?? query.project_id,
      status: query.status || undefined,
      approval_status: query.approval_status || undefined,
      personnel_scope: filterScopes.value.length ? filterScopes.value.join(',') : undefined,
    })
    tasks.value = result.items
    total.value = result.total
    resetExpandedTasks()
  } finally { loading.value = false }
}

async function loadOptions() {
  [projects.value, users.value, departments.value, organizations.value] = await Promise.all([
    props.projectId ? getProject(props.projectId).then(project => [project]) : getAllProjects(),
    getUserOptions(), getDepartmentOptions(), getOrganizationTree(),
  ])
}

async function applyFilters() {
  query.page = 1
  await load()
}

async function loadOwnerOptions(projectId: number) {
  const members = await getProjectMembers(projectId)
  const ids = new Set(members.map((item) => item.user_id))
  projectMemberOptions.value = users.value.filter((item) => ids.has(item.id))
}

async function loadProjectTaskOptions(projectId: number) {
  projectTasks.value = await getAllTasks({ project_id: projectId, managed_project_scope: true })
}

async function changeProject(projectId: number) {
  form.parent_id = undefined
  form.owner_ids = []
  await Promise.all([loadOwnerOptions(projectId), loadProjectTaskOptions(projectId)])
  const project = projects.value.find((item) => item.id === projectId)
  if (project) {
    form.planned_start = project.planned_start
    form.planned_end = project.planned_end
  }
}

function changeParent(parentId?: number) {
  const parent = projectTasks.value.find((item) => item.id === parentId)
  if (!parent) return
  const allowed = new Set(parent.owner_ids)
  form.owner_ids = form.owner_ids.filter((id) => allowed.has(id))
  if (!form.owner_ids.length) form.owner_ids = [...parent.owner_ids]
  form.planned_start = parent.planned_start
  form.planned_end = parent.planned_end
}

async function openCreate(parent?: Task) {
  if (!approvedProjects.value.length) return ElMessage.warning('只有自己负责且已通过审批的项目可以新增任务')
  editingId.value = undefined
  editingTextOnly.value = false
  resetHours()
  editingProjectName.value = ''
  Object.assign(form, emptyForm(), parent
    ? { project_id: parent.project_id, parent_id: parent.id, owner_ids: [...parent.owner_ids], planned_start: parent.planned_start, planned_end: parent.planned_end }
    : { project_id: approvedProjects.value[0].id, planned_start: approvedProjects.value[0].planned_start, planned_end: approvedProjects.value[0].planned_end })
  await Promise.all([loadOwnerOptions(form.project_id), loadProjectTaskOptions(form.project_id)])
  dialogVisible.value = true
}

async function openEdit(row: Task) {
  editingId.value = row.id
  editingTextOnly.value = row.approval_status === 'approved' || row.status === 'completed'
  editingProjectName.value = row.project_name || `项目 #${row.project_id}`
  Object.assign(form, {
    project_id: row.project_id, parent_id: row.parent_id, name: row.name,
    owner_ids: [...row.owner_ids], planned_start: row.planned_start,
    planned_end: row.planned_end, estimated_hours: Number(row.estimated_hours),
    description: row.description || '', remark: row.remark || '',
  })
  await Promise.all([loadOwnerOptions(row.project_id), loadProjectTaskOptions(row.project_id)])
  dialogVisible.value = true
}

async function save() {
  if (saving.value) return
  if (!editingTextOnly.value) {
    if (!(await formRef.value?.validate().catch(() => false))) return
    if (!editingId.value && !hoursManual.value && (hoursLoading.value || !hoursEstimate.value)) return ElMessage.warning('请等待默认工时计算完成，或手动填写工时')
    if (!isPositiveHalfHour(form.estimated_hours)) return ElMessage.warning('任务计划工时必须为大于 0 的 0.5 小时整数倍')
    if (form.planned_end < form.planned_start) return ElMessage.warning('计划结束时间不能早于开始时间')
    if (selectedParent.value && Number(form.estimated_hours) > remainingParentHours.value) return ElMessage.warning(`子任务计划工时不能超过父任务剩余额度 ${remainingParentHours.value}h`)
  }
  saving.value = true
  try {
    const action = !editingId.value && !form.parent_id ? '提交部门主管审批' : '保存任务'
    if (!(await confirmAction(`项目：${selectedProject.value?.name || editingProjectName.value}\n任务：${form.name}\n计划：${form.planned_start} 至 ${form.planned_end}\n预计工时：${form.estimated_hours}h\n确认${action}？`, action, `确认${action}`))) return
    const payload = { ...form }
    if (editingId.value) {
      const { project_id: _projectId, ...updatePayload } = payload
      await updateTask(editingId.value, editingTextOnly.value
        ? { description: form.description, remark: form.remark }
        : updatePayload)
    } else await createTask(payload)
    ElMessage.success(!editingId.value && !form.parent_id ? '父任务已提交部门主管审批，通过后可安排子任务和预约工时' : '任务已保存')
    dialogVisible.value = false
    await load()
    emit('changed')
  } catch { /* API interceptor displays validation and quota errors. */ }
  finally { saving.value = false }
}

async function remove(row: Task) {
  if (!(await confirmAction(`确认删除任务“${row.name}”吗？`, '删除任务', '确认删除'))) return
  await deleteTask(row.id)
  ElMessage.success('任务已删除')
  await load()
  emit('changed')
}

async function editRemark(row: Task) {
  const result = await ElMessageBox.prompt('任务项目成员可以维护备注；已通过审批的任务不能修改成员、计划工时等核心字段。', '编辑任务备注', { inputType: 'textarea', inputValue: row.remark || '', confirmButtonText: '下一步' }).catch(() => null)
  if (!result || !(await confirmAction(`确认保存任务“${row.name}”的备注？`, '保存任务备注', '确认保存'))) return
  const { value } = result
  await updateTask(row.id, { remark: value || '' })
  ElMessage.success('备注已保存')
  await load()
}

async function openReview(row: Task) {
  try {
    reviewTask.value = await getTask(row.id)
    reviewNote.value = ''
    reviewVisible.value = true
  } catch { /* API interceptor displays the error. */ }
}

async function decide(approved: boolean) {
  if (!reviewTask.value || reviewBusy.value) return
  const note = reviewNote.value.trim()
  if (!approved && !note) return ElMessage.warning('请填写驳回原因')
  reviewBusy.value = true
  try {
    if (!(await confirmAction(`任务：${reviewTask.value.name}\n项目：${reviewTask.value.project_name}\n预计工时：${reviewTask.value.estimated_hours}h\n${approved ? '批准后可创建子任务、预约和执行。' : `驳回原因：${note}`}\n确认${approved ? '批准' : '驳回'}该父任务？`, '父任务审批', approved ? '确认批准' : '确认驳回'))) return
    if (approved) await approveTask(reviewTask.value.id, note || undefined)
    else await rejectTask(reviewTask.value.id, note)
    ElMessage.success(approved ? '父任务审批已通过' : '父任务已驳回')
    reviewVisible.value = false
    await load()
    emit('changed')
  } catch { /* Keep the dialog open so the user can read the API error. */ }
  finally { reviewBusy.value = false }
}

async function resubmit(row: Task) {
  if (submittingId.value) return
  if (!(await confirmAction(`确认将父任务“${row.name}”重新提交部门主管审批？`, '重新提交审批'))) return
  submittingId.value = row.id
  try {
    await submitTask(row.id)
    ElMessage.success('已重新提交部门主管审批')
    await load()
    emit('changed')
  } catch { /* API interceptor displays the error. */ }
  finally { submittingId.value = undefined }
}

onMounted(async () => { try { await loadOptions(); await load() } catch { /* API interceptor displays the error. */ } })
</script>

<template>
  <div class="page-shell" :class="{embedded: props.projectId}">
    <header class="page-header">
      <div><h1 class="page-title">{{props.projectId ? '项目任务' : '任务管理'}}</h1></div>
      <el-button v-if="approvedProjects.length" type="primary" @click="openCreate()">新增任务</el-button>
    </header>
    <section class="surface filter-bar">
      <el-select v-if="!props.projectId" v-model="query.project_id" clearable filterable placeholder="项目" style="width:210px"><el-option v-for="item in projects" :key="item.id" :label="`${item.code} · ${item.name}`" :value="item.id"/></el-select>
        <PersonnelScopeCascader v-model="filterScopes" :users="users" :departments="departments" :organizations="organizations" placeholder="项目成员" />
      <el-select v-model="query.status" clearable placeholder="任务状态" style="width:130px"><el-option v-for="item in filterStatuses" :key="item" :label="statusLabel[item]" :value="item"/></el-select>
      <el-select v-model="query.approval_status" clearable placeholder="审批状态" style="width:170px"><el-option v-for="(label,value) in approvalLabels" :key="value" :label="label" :value="value"/></el-select>
      <el-button @click="applyFilters">查询</el-button>
    </section>
    <section class="surface table-card">
      <el-table v-loading="loading" :data="visibleTaskRows" row-key="id" :span-method="taskSpanMethod" table-layout="fixed" :header-cell-style="{ textAlign: 'center' }" :cell-style="{ textAlign: 'center' }">
        <el-table-column prop="project_name" label="项目名称" min-width="145" align="center" show-overflow-tooltip><template #default="{row}"><strong class="project-name">{{row.project_name}}</strong></template></el-table-column>
        <el-table-column prop="name" label="任务名称" min-width="185" align="center" header-align="center">
          <template #default="{row}">
            <div class="task-cell" :style="{paddingInline:`min(${row.treeLevel*12}px, 16%)`}">
              <button v-if="row.hasChildren" class="tree-toggle" :title="expandedTaskIds.has(row.id)?'折叠子任务':'展开子任务'" :aria-expanded="expandedTaskIds.has(row.id)" @click="toggleTask(row)"><el-icon><ArrowDown v-if="expandedTaskIds.has(row.id)"/><ArrowRight v-else/></el-icon></button>
              <span v-else class="tree-spacer" aria-hidden="true"></span>
              <el-tooltip placement="top" :show-after="250">
                <template #content><span class="task-name-full">{{row.name}}</span></template>
                <span class="task-name" tabindex="0">{{row.name}}</span>
              </el-tooltip>
              <span class="tree-spacer" aria-hidden="true"></span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="owner_name" label="项目成员" min-width="135" show-overflow-tooltip/>
        <el-table-column label="计划日期" min-width="175" align="center"><template #default="{row}"><span class="period-cell">{{formatDate(row.planned_start)}}<i>至</i>{{formatDate(row.planned_end)}}</span></template></el-table-column>
        <el-table-column label="预计工时" min-width="100" align="center"><template #default="{row}">{{row.estimated_hours}}h</template></el-table-column>
        <el-table-column label="状态" min-width="100" align="center"><template #default="{row}"><el-tooltip :disabled="row.effective_status!=='delayed'" content="已逾期任务只有完成后才会显示已完成" placement="top"><el-tag :type="row.effective_status==='delayed'?'danger':row.effective_status==='completed'?'success':'info'" effect="plain">{{statusLabel[row.effective_status]}}</el-tag></el-tooltip></template></el-table-column>
        <el-table-column label="审批" min-width="145" align="center"><template #default="{row}"><el-tooltip :disabled="!row.approval_note" :content="row.approval_note || ''" placement="top"><el-tag :type="row.approval_status==='pending'?'warning':row.approval_status==='rejected'?'danger':row.approval_status==='approved'?'success':'info'" effect="plain">{{approvalLabels[row.approval_status]}}</el-tag></el-tooltip></template></el-table-column>
        <el-table-column label="操作" fixed="right" min-width="230" align="center"><template #default="{row}">
          <el-button v-if="row.can_review" link type="primary" @click="openReview(row)">审批</el-button>
          <el-button v-if="row.can_manage && row.approval_status==='rejected'" link type="primary" :loading="submittingId===row.id" @click="resubmit(row)">重新提交</el-button>
          <el-button v-if="row.can_manage && isExecutable(row)" link @click="openCreate(row)">添加子任务</el-button>
          <el-button v-if="row.can_manage && row.can_edit" link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-else-if="row.can_edit" link type="primary" @click="editRemark(row)">编辑备注</el-button>
          <el-button v-if="row.can_delete" link type="danger" @click="remove(row)">删除</el-button>
          <el-button v-if="canExecuteTask(row) && !row.hasChildren" link type="primary" @click="router.push({path:'/executions',query:{task_id:row.id,project_id:row.project_id}})">执行记录</el-button>
        </template></el-table-column>
      </el-table>
      <div class="table-footer"><el-pagination v-model:current-page="query.page" v-model:page-size="query.page_size" :total="total" :page-sizes="[50,100,200]" layout="total, sizes, prev, pager, next" @change="load"/></div>
    </section>
    <el-dialog v-model="dialogVisible" :title="editingId?'编辑任务':'新增任务'" width="720px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="editingTextOnly ? {} : rules" label-position="top">
        <el-alert v-if="editingTextOnly" class="project-window" type="info" :closable="false" show-icon title="已审批或已完成的任务只能修改描述和备注。"/>
        <div class="form-grid">
          <el-form-item label="所属项目" prop="project_id"><el-input v-if="editingId" :model-value="editingProjectName" disabled/><el-select v-else v-model="form.project_id" filterable style="width:100%" @change="changeProject"><el-option v-for="item in approvedProjects" :key="item.id" :label="item.name" :value="item.id"/></el-select></el-form-item>
          <el-form-item label="父任务"><el-select v-model="form.parent_id" :disabled="editingTextOnly || Boolean(editingId && !form.parent_id)" :clearable="!editingId" placeholder="不选择即新建顶层父任务" style="width:100%" @change="changeParent"><el-option v-for="item in parentOptions" :key="item.id" :label="item.name" :value="item.id"/></el-select></el-form-item>
          <el-alert v-if="selectedProject" class="project-window" type="info" :closable="false" show-icon :title="`项目周期：${formatDate(selectedProject.planned_start)} 至 ${formatDate(selectedProject.planned_end)}；项目总工时：${selectedProject.budget_hours}h；顶级任务已分配：${allocatedProjectHours}h`"/>
          <el-alert v-if="selectedParent && !editingTextOnly" class="project-window" type="info" :closable="false" show-icon :title="`父任务预计工时：${selectedParent.estimated_hours}h；可分配额度：${remainingParentHours}h（已完成子任务仍占用已分配工时）`"/>
          <el-form-item label="任务名称" prop="name"><el-input v-model="form.name" :disabled="editingTextOnly"/></el-form-item>
          <el-form-item label="项目成员" prop="owner_ids"><el-select v-model="form.owner_ids" :disabled="editingTextOnly" multiple filterable collapse-tags collapse-tags-tooltip style="width:100%"><el-option v-for="item in ownerOptions" :key="item.id" :label="`${item.name} (${item.employee_no})`" :value="item.id"/></el-select></el-form-item>
          <el-form-item label="计划开始" prop="planned_start"><el-date-picker v-model="form.planned_start" :disabled="editingTextOnly" type="date" value-format="YYYY-MM-DD" style="width:100%"/></el-form-item>
          <el-form-item label="计划结束" prop="planned_end"><el-date-picker v-model="form.planned_end" :disabled="editingTextOnly" type="date" value-format="YYYY-MM-DD" style="width:100%"/></el-form-item>
          <el-form-item label="任务计划工时" prop="estimated_hours"><el-input-number v-model="hoursInput" :disabled="editingTextOnly" :min="editingId?0.5:0" :step="0.5" step-strictly :precision="1" style="width:100%"/></el-form-item>
        </div>
        <PlannedHoursHint v-if="!editingId" :estimate="hoursEstimate" :loading="hoursLoading" :manual="hoursManual" :error="hoursError" @reset="useDefaultHours"/>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="3"/></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="2"/></el-form-item>
        <div class="form-hint">项目成员支持多选；子任务只能选择父任务已有的项目成员。顶级任务工时合计不能超过项目工时，同级子任务工时合计不能超过父任务工时。</div>
        <el-alert v-if="!editingId" class="approval-hint" :closable="false" type="info" show-icon :title="form.parent_id ? '子任务无需单独审批，保存后可预约工时。' : '父任务保存后提交项目所属部门主管审批；审批通过后才能创建子任务、预约和执行。'"/>
      </el-form>
      <template #footer><el-button :disabled="saving" @click="dialogVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="save">{{!editingId && !form.parent_id ? '提交部门主管审批' : '保存'}}</el-button></template>
    </el-dialog>
    <el-dialog v-model="reviewVisible" title="父任务审批" width="640px" :close-on-click-modal="!reviewBusy" :close-on-press-escape="!reviewBusy" :show-close="!reviewBusy" destroy-on-close>
      <template v-if="reviewTask">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="所属项目">{{reviewTask.project_name}}</el-descriptions-item>
          <el-descriptions-item label="任务名称">{{reviewTask.name}}</el-descriptions-item>
          <el-descriptions-item label="项目成员">{{reviewTask.owner_names.join('、')}}</el-descriptions-item>
          <el-descriptions-item label="计划日期">{{formatDate(reviewTask.planned_start)}} 至 {{formatDate(reviewTask.planned_end)}}</el-descriptions-item>
          <el-descriptions-item label="预计工时">{{reviewTask.estimated_hours}}h</el-descriptions-item>
          <el-descriptions-item label="描述"><span class="review-text">{{reviewTask.description || '无'}}</span></el-descriptions-item>
          <el-descriptions-item label="备注"><span class="review-text">{{reviewTask.remark || '无'}}</span></el-descriptions-item>
        </el-descriptions>
        <el-input v-model="reviewNote" class="approval-hint" type="textarea" :rows="3" maxlength="2000" show-word-limit placeholder="审批意见（驳回时必填）"/>
        <el-alert v-if="!reviewTask.can_review" class="approval-hint" type="info" :closable="false" title="该任务已处理或当前账号不具备审批权限，请刷新任务列表。"/>
      </template>
      <template #footer>
        <el-button :disabled="reviewBusy" @click="reviewVisible=false">关闭</el-button>
        <el-button v-if="reviewTask?.can_review" type="danger" :loading="reviewBusy" @click="decide(false)">驳回</el-button>
        <el-button v-if="reviewTask?.can_review" type="primary" :loading="reviewBusy" @click="decide(true)">通过审批</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.embedded{gap:16px}.embedded .page-header{margin:4px 0}.embedded .page-title{font-size:18px}.embedded .table-card{box-shadow:none;border:0;padding:0}.embedded .filter-bar{box-shadow:none;background:var(--el-fill-color-light)}
.approval-hint{margin-top:16px}.review-text{white-space:pre-wrap;overflow-wrap:anywhere}
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 18px}.project-window{grid-column:1/-1;margin-bottom:18px}.form-hint{margin-top:-4px;color:#9aa3b1;font-size:11px}
.project-name{display:block;overflow:hidden;color:#334155;font-size:13px;font-weight:650;text-overflow:ellipsis;white-space:nowrap}
/* Equal side slots keep the name centered under its header even with a tree toggle.
   Symmetric, capped nesting space keeps deep tasks readable in a narrow column. */
.task-cell{display:grid;width:100%;min-width:0;grid-template-columns:24px minmax(0,1fr) 24px;align-items:center;gap:7px;color:#465468}
.task-name{display:block;width:100%;min-width:0;overflow:hidden;text-align:center;text-overflow:ellipsis;white-space:nowrap}
.task-name-full{display:block;max-width:min(420px,calc(100vw - 48px));white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.6}
.task-name:focus-visible,.tree-toggle:focus-visible{outline:2px solid #527fa6;outline-offset:-2px;border-radius:4px}
.tree-toggle{display:grid;width:24px;height:24px;place-items:center;border:0;border-radius:7px;background:transparent;color:#718096;cursor:pointer}.tree-toggle:hover{background:#edf3f8;color:#315f8e}.tree-spacer{width:24px}
.period-cell{display:inline-grid;grid-template-columns:auto auto auto;gap:5px;align-items:center;white-space:nowrap}.period-cell i{color:#a0a9b6;font-size:11px;font-style:normal}
</style>
