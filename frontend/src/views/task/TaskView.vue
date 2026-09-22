<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createTask, deleteTask, getAllTasks, getTasks, updateTask } from '@/api/task'
import { getAllProjects, getProjectMembers } from '@/api/project'
import { getUserOptions } from '@/api/user'
import { getDepartmentOptions, getOrganizationTree } from '@/api/organization'
import type { DepartmentOption, OrganizationNode } from '@/types/organization'
import type { Project } from '@/types/project'
import type { Task, TaskPayload } from '@/types/task'
import type { UserOption } from '@/types/user'
import { formatDate } from '@/utils/format'
import { useUserStore } from '@/stores/user'

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
const organizationScope = ref('')
const projectMemberOptions = ref<UserOption[]>([])
const query = reactive({
  page: 1, page_size: 100, project_id: undefined as number | undefined,
  owner_id: undefined as number | undefined,
  department_id: undefined as number | undefined,
  organization_id: undefined as number | undefined,
  status: '',
})
const dialogVisible = ref(false)
const editingId = ref<number>()
const editingProjectName = ref('')
const formRef = ref<FormInstance>()
const emptyForm = (): TaskPayload => ({
  project_id: 0, parent_id: undefined, name: '', owner_ids: [],
  planned_start: '', planned_end: '', estimated_hours: 0,
  description: '', remark: '',
})
const form = reactive<TaskPayload>(emptyForm())
const rules: FormRules = {
  project_id: [{ required: true, message: '请选择项目' }],
  name: [{ required: true, message: '请输入任务名称' }],
  owner_ids: [{ required: true, type: 'array', min: 1, message: '请至少选择一名项目成员' }],
  planned_start: [{ required: true, message: '请选择计划开始日期' }],
  planned_end: [{ required: true, message: '请选择计划结束日期' }],
}
const filterStatuses = ['not_started', 'running', 'completed', 'delayed']
const statusLabel: Record<string, string> = { not_started: '未开始', running: '进行中', completed: '已完成', delayed: '已逾期' }
const canManageProject = (project?: Project) => Boolean(project?.can_manage)
const canExecuteTask = (task: Task) => task.owner_ids.includes(userStore.profile?.id || -1)
  || Boolean(userStore.profile?.roles.some(role => ['super_admin', 'department_manager'].includes(role)))
const manageableProjects = computed(() => projects.value.filter(canManageProject))
const approvedProjects = computed(() => manageableProjects.value.filter((item) => item.approval_status === 'approved' && !['Completed', 'Cancelled'].includes(item.status)))
const selectedProject = computed(() => projects.value.find((item) => item.id === form.project_id))
const selectedParent = computed(() => projectTasks.value.find((item) => item.id === form.parent_id))
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
    && item.status === 'not_started'
    && Number(item.booked_hours) === 0,
))
const ownerOptions = computed(() => {
  if (!selectedParent.value) return projectMemberOptions.value
  const allowed = new Set(selectedParent.value.owner_ids)
  return projectMemberOptions.value.filter((item) => allowed.has(item.id))
})
const treeTasks = computed(() => {
  const nodes = new Map<number, Task>()
  tasks.value.forEach((item) => nodes.set(item.id, { ...item, children: [] }))
  const roots: Task[] = []
  nodes.forEach((item) => {
    const parent = item.parent_id ? nodes.get(item.parent_id) : undefined
    if (parent) parent.children?.push(item)
    else roots.push(item)
  })
  return roots
})
const organizationScopeOptions = computed(() => {
  const options: Array<{ value: string; label: string }> = departments.value.map((item) => ({
    value: `department:${item.id}`,
    label: `部门 · ${item.name}`,
  }))
  const walk = (nodes: OrganizationNode[], prefix = '') => nodes.forEach((node) => {
    options.push({
      value: `organization:${node.id}`,
      label: `组织 · ${prefix}${node.name}`,
    })
    walk(node.children || [], `${prefix}${node.name} / `)
  })
  walk(organizations.value)
  return options
})

function syncOrganizationScope() {
  query.department_id = undefined
  query.organization_id = undefined
  if (!organizationScope.value) return
  const [kind, rawId] = organizationScope.value.split(':')
  const id = Number(rawId)
  if (kind === 'department') query.department_id = id
  if (kind === 'organization') query.organization_id = id
}

async function load() {
  loading.value = true
  try {
    const result = await getTasks({
      ...query,
      status: query.status || undefined,
    })
    tasks.value = result.items
    total.value = result.total
  } finally { loading.value = false }
}

async function loadOptions() {
  [projects.value, users.value, departments.value, organizations.value] = await Promise.all([
    getAllProjects(), getUserOptions(), getDepartmentOptions(), getOrganizationTree(),
  ])
}

async function applyFilters() {
  syncOrganizationScope()
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
  editingProjectName.value = ''
  Object.assign(form, emptyForm(), parent
    ? { project_id: parent.project_id, parent_id: parent.id, owner_ids: [...parent.owner_ids], planned_start: parent.planned_start, planned_end: parent.planned_end }
    : { project_id: approvedProjects.value[0].id, planned_start: approvedProjects.value[0].planned_start, planned_end: approvedProjects.value[0].planned_end })
  await Promise.all([loadOwnerOptions(form.project_id), loadProjectTaskOptions(form.project_id)])
  dialogVisible.value = true
}

async function openEdit(row: Task) {
  editingId.value = row.id
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
  if (!(await formRef.value?.validate())) return
  if (form.planned_end < form.planned_start) return ElMessage.warning('计划结束时间不能早于开始时间')
  const payload = { ...form }
  if (editingId.value) {
    const { project_id: _projectId, ...updatePayload } = payload
    await updateTask(editingId.value, updatePayload)
  } else await createTask(payload)
  ElMessage.success('任务已保存')
  dialogVisible.value = false
  await load()
}

async function remove(row: Task) {
  await ElMessageBox.confirm(`确认删除任务“${row.name}”吗？`, '删除任务', { type: 'warning' })
  await deleteTask(row.id)
  ElMessage.success('任务已删除')
  await load()
}

async function editRemark(row: Task) {
  const { value } = await ElMessageBox.prompt('任务项目成员可以维护备注；项目成员、计划工时等核心字段由项目负责人维护。', '编辑任务备注', { inputType: 'textarea', inputValue: row.remark || '' })
  await updateTask(row.id, { remark: value || '' })
  ElMessage.success('备注已保存')
  await load()
}

onMounted(async () => { await loadOptions(); await load() })
</script>

<template>
  <div class="page-shell">
    <header class="page-header">
      <div><h1 class="page-title">任务管理</h1><p class="page-subtitle">展示本人、参与项目及权限范围内的任务；任务状态以最新执行记录为准，项目完成由负责人手动确认。</p></div>
      <el-button v-if="approvedProjects.length" type="primary" @click="openCreate()">新增任务</el-button>
    </header>
    <section class="surface filter-bar">
      <el-select v-model="query.project_id" clearable filterable placeholder="项目" style="width:210px"><el-option v-for="item in projects" :key="item.id" :label="`${item.code} · ${item.name}`" :value="item.id"/></el-select>
      <el-select v-model="organizationScope" clearable filterable placeholder="部门 / 组织" style="width:220px" @change="syncOrganizationScope"><el-option v-for="item in organizationScopeOptions" :key="item.value" :label="item.label" :value="item.value"/></el-select>
      <el-select v-model="query.owner_id" clearable filterable placeholder="项目成员（姓名 / 工号）" style="width:230px"><el-option v-for="item in users" :key="item.id" :label="`${item.name}（${item.employee_no}）`" :value="item.id"/></el-select>
      <el-select v-model="query.status" clearable placeholder="任务状态" style="width:130px"><el-option v-for="item in filterStatuses" :key="item" :label="statusLabel[item]" :value="item"/></el-select>
      <el-button @click="applyFilters">查询</el-button>
    </section>
    <section class="surface table-card">
      <el-table v-loading="loading" :data="treeTasks" row-key="id" default-expand-all>
        <el-table-column prop="name" label="任务名称" min-width="220"><template #default="{row}"><span class="task-name" :class="{child:row.parent_id}">{{row.name}}</span></template></el-table-column>
        <el-table-column prop="project_name" label="项目" min-width="160" show-overflow-tooltip/>
        <el-table-column prop="owner_name" label="项目成员" min-width="130"/>
        <el-table-column label="计划日期" width="220"><template #default="{row}">{{formatDate(row.planned_start)}} 至 {{formatDate(row.planned_end)}}</template></el-table-column>
        <el-table-column label="预计工时" width="95"><template #default="{row}">{{row.estimated_hours}}h</template></el-table-column>
        <el-table-column label="状态" width="95"><template #default="{row}"><el-tag :type="row.effective_status==='delayed'?'danger':row.effective_status==='completed'?'success':'info'" effect="plain">{{statusLabel[row.effective_status]}}</el-tag></template></el-table-column>
        <el-table-column label="操作" fixed="right" width="265"><template #default="{row}"><el-button v-if="row.status==='not_started'&&Number(row.booked_hours)===0&&row.can_manage" link @click="openCreate(row)">添加子任务</el-button><el-button v-if="row.can_manage && row.can_edit" link type="primary" @click="openEdit(row)">编辑</el-button><el-button v-else-if="row.can_edit" link type="primary" @click="editRemark(row)">编辑备注</el-button><el-button v-if="row.can_delete" link type="danger" @click="remove(row)">删除</el-button><el-button v-if="canExecuteTask(row) && !row.children?.length" link type="primary" @click="router.push({path:'/executions',query:{task_id:row.id,project_id:row.project_id}})">执行记录</el-button></template></el-table-column>
      </el-table>
      <div class="table-footer"><el-pagination v-model:current-page="query.page" v-model:page-size="query.page_size" :total="total" :page-sizes="[50,100,200]" layout="total, sizes, prev, pager, next" @change="load"/></div>
    </section>
    <el-dialog v-model="dialogVisible" :title="editingId?'编辑任务':'新增任务'" width="720px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <div class="form-grid">
          <el-form-item label="所属项目" prop="project_id"><el-input v-if="editingId" :model-value="editingProjectName" disabled/><el-select v-else v-model="form.project_id" filterable style="width:100%" @change="changeProject"><el-option v-for="item in approvedProjects" :key="item.id" :label="item.name" :value="item.id"/></el-select></el-form-item>
          <el-form-item label="父任务"><el-select v-model="form.parent_id" clearable style="width:100%" @change="changeParent"><el-option v-for="item in parentOptions" :key="item.id" :label="item.name" :value="item.id"/></el-select></el-form-item>
          <el-alert v-if="selectedProject" class="project-window" type="info" :closable="false" show-icon :title="`项目计划周期：${formatDate(selectedProject.planned_start)} 至 ${formatDate(selectedProject.planned_end)}`"/>
          <el-form-item label="任务名称" prop="name"><el-input v-model="form.name"/></el-form-item>
          <el-form-item label="项目成员" prop="owner_ids"><el-select v-model="form.owner_ids" multiple filterable collapse-tags collapse-tags-tooltip style="width:100%"><el-option v-for="item in ownerOptions" :key="item.id" :label="`${item.name} (${item.employee_no})`" :value="item.id"/></el-select></el-form-item>
          <el-form-item label="计划开始" prop="planned_start"><el-date-picker v-model="form.planned_start" type="date" value-format="YYYY-MM-DD" style="width:100%"/></el-form-item>
          <el-form-item label="计划结束" prop="planned_end"><el-date-picker v-model="form.planned_end" type="date" value-format="YYYY-MM-DD" style="width:100%"/></el-form-item>
          <el-form-item label="预计工时"><el-input-number v-model="form.estimated_hours" :min="0" :precision="1" style="width:100%"/></el-form-item>
        </div>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="3"/></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="2"/></el-form-item>
        <div class="form-hint">项目成员支持多选；子任务只能选择父任务已有的项目成员。顶级任务工时合计不能超过项目工时，同级子任务工时合计不能超过父任务工时。</div>
      </el-form>
      <template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 18px}.project-window{grid-column:1/-1;margin-bottom:18px}.task-name{font-weight:600;color:#39465a}.task-name.child{font-weight:400;color:#5f6b7c}.form-hint{margin-top:-4px;color:#9aa3b1;font-size:11px}
</style>
