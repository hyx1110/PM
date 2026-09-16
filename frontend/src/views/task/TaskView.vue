<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createTask, deleteTask, getTasks, updateTask } from '@/api/task'
import { getProjectMembers, getProjects } from '@/api/project'
import { getUserOptions } from '@/api/user'
import { getDepartments, getOrganizationTree } from '@/api/organization'
import type { Department, OrganizationNode } from '@/types/organization'
import type { Project } from '@/types/project'
import type { Task, TaskPayload } from '@/types/task'
import type { UserOption } from '@/types/user'
import { formatDateTime, toApiDateTime } from '@/utils/format'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const loading = ref(false)
const tasks = ref<Task[]>([])
const total = ref(0)
const projects = ref<Project[]>([])
const users = ref<UserOption[]>([])
const ownerOptions = ref<UserOption[]>([])
const departments = ref<Department[]>([])
const organizations = ref<OrganizationNode[]>([])
const query = reactive({
  page: 1, page_size: 100, project_id: undefined as number | undefined,
  status: '', department_id: undefined as number | undefined,
  organization_id: undefined as number | undefined, employee_no: '', name: '',
})
const dialogVisible = ref(false)
const editingId = ref<number>()
const formRef = ref<FormInstance>()
const emptyForm = (): TaskPayload => ({
  project_id: 0, parent_id: undefined, name: '', task_type: 'Project', owner_ids: [],
  planned_start: '', planned_end: '', estimated_hours: 0, status: 'not_started',
  description: '', remark: '',
})
const form = reactive<TaskPayload>(emptyForm())
const rules: FormRules = {
  project_id: [{ required: true, message: '请选择项目' }],
  name: [{ required: true, message: '请输入任务名称' }],
  owner_ids: [{ required: true, type: 'array', min: 1, message: '请至少选择一名负责人' }],
  planned_start: [{ required: true, message: '请选择计划开始时间' }],
  planned_end: [{ required: true, message: '请选择计划结束时间' }],
}
const statuses = ['not_started', 'running', 'completed', 'suspended', 'cancelled']
const statusLabel: Record<string, string> = { not_started: '未开始', running: '进行中', completed: '已完成', suspended: '已暂停', cancelled: '已取消', delayed: '已延期' }
const taskTypes = ['Project', 'Routine', 'Training', 'Leave', 'Other']
const canManageProject = (project?: Project) => Boolean(
  project && project.manager_id === userStore.profile?.id && userStore.profile?.roles.includes('project_manager'),
)
const canEditTask = (task: Task) => task.owner_ids.includes(userStore.profile?.id || -1)
const manageableProjects = computed(() => projects.value.filter(canManageProject))
const approvedProjects = computed(() => manageableProjects.value.filter((item) => item.approval_status === 'approved' && !['Completed', 'Cancelled'].includes(item.status)))
const parentOptions = computed(() => tasks.value.filter((item) => item.project_id === form.project_id && !item.parent_id && item.id !== editingId.value))
const flatOrganizations = computed(() => {
  const result: Array<OrganizationNode & { label: string }> = []
  const walk = (nodes: OrganizationNode[], prefix = '') => nodes.forEach((node) => {
    result.push({ ...node, label: `${prefix}${node.name}` })
    walk(node.children || [], `${prefix}　`)
  })
  walk(organizations.value)
  return result
})
const treeTasks = computed(() => {
  const visibleIds = new Set(tasks.value.map((item) => item.id))
  const roots = tasks.value.filter((item) => !item.parent_id || !visibleIds.has(item.parent_id)).map((item) => ({ ...item, children: [] as Task[] }))
  const rootMap = new Map(roots.map((item) => [item.id, item]))
  tasks.value.filter((item) => item.parent_id).forEach((item) => rootMap.get(item.parent_id!)?.children?.push({ ...item }))
  return roots
})

async function load() {
  loading.value = true
  try {
    const result = await getTasks({
      ...query,
      status: query.status || undefined,
      employee_no: query.employee_no || undefined,
      name: query.name || undefined,
    })
    tasks.value = result.items
    total.value = result.total
  } finally { loading.value = false }
}

async function loadOptions() {
  [projects.value, users.value, departments.value, organizations.value] = await Promise.all([
    getProjects({ page: 1, page_size: 200 }).then((result) => result.items),
    getUserOptions(), getDepartments(), getOrganizationTree(),
  ])
}

async function loadOwnerOptions(projectId: number) {
  const members = await getProjectMembers(projectId)
  const ids = new Set(members.map((item) => item.user_id))
  ownerOptions.value = users.value.filter((item) => ids.has(item.id))
}

async function changeProject(projectId: number) {
  form.parent_id = undefined
  form.owner_ids = []
  await loadOwnerOptions(projectId)
}

async function openCreate(parent?: Task) {
  if (!approvedProjects.value.length) return ElMessage.warning('只有自己负责且已通过审批的项目可以新增任务')
  editingId.value = undefined
  Object.assign(form, emptyForm(), parent
    ? { project_id: parent.project_id, parent_id: parent.id }
    : { project_id: approvedProjects.value[0].id })
  await loadOwnerOptions(form.project_id)
  dialogVisible.value = true
}

async function openEdit(row: Task) {
  editingId.value = row.id
  Object.assign(form, {
    project_id: row.project_id, parent_id: row.parent_id, name: row.name,
    task_type: row.task_type, owner_ids: [...row.owner_ids], planned_start: row.planned_start,
    planned_end: row.planned_end, estimated_hours: Number(row.estimated_hours), status: row.status,
    description: row.description || '', remark: row.remark || '',
  })
  await loadOwnerOptions(row.project_id)
  dialogVisible.value = true
}

async function save() {
  if (!(await formRef.value?.validate())) return
  if (form.planned_end < form.planned_start) return ElMessage.warning('计划结束时间不能早于开始时间')
  const payload = { ...form, planned_start: toApiDateTime(form.planned_start)!, planned_end: toApiDateTime(form.planned_end)! }
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

onMounted(async () => { await loadOptions(); await load() })
</script>

<template>
  <div class="page-shell">
    <header class="page-header">
      <div><h1 class="page-title">任务管理</h1><p class="page-subtitle">所有人可查看全部任务；只有任务负责人可以编辑任务。</p></div>
      <el-button v-if="approvedProjects.length" type="primary" @click="openCreate()">新增任务</el-button>
    </header>
    <section class="surface filter-bar">
      <el-select v-model="query.project_id" clearable filterable placeholder="项目" style="width:210px"><el-option v-for="item in projects" :key="item.id" :label="`${item.code} · ${item.name}`" :value="item.id"/></el-select>
      <el-select v-model="query.department_id" clearable placeholder="部门" style="width:150px"><el-option v-for="item in departments" :key="item.id" :label="item.name" :value="item.id"/></el-select>
      <el-select v-model="query.organization_id" clearable filterable placeholder="组织" style="width:170px"><el-option v-for="item in flatOrganizations" :key="item.id" :label="item.label" :value="item.id"/></el-select>
      <el-input v-model="query.employee_no" clearable placeholder="负责人工号" style="width:145px"/>
      <el-input v-model="query.name" clearable placeholder="负责人姓名" style="width:145px"/>
      <el-select v-model="query.status" clearable placeholder="任务状态" style="width:130px"><el-option v-for="item in statuses" :key="item" :label="statusLabel[item]" :value="item"/></el-select>
      <el-button @click="query.page=1;load()">查询</el-button>
    </section>
    <section class="surface table-card">
      <el-table v-loading="loading" :data="treeTasks" row-key="id" default-expand-all>
        <el-table-column prop="name" label="任务名称" min-width="220"><template #default="{row}"><span class="task-name" :class="{child:row.parent_id}">{{row.name}}</span></template></el-table-column>
        <el-table-column prop="project_name" label="项目" min-width="160" show-overflow-tooltip/>
        <el-table-column prop="task_type" label="类型" width="100"/>
        <el-table-column prop="owner_name" label="负责人" min-width="130"/>
        <el-table-column label="计划时间" width="285"><template #default="{row}">{{formatDateTime(row.planned_start)}} 至 {{formatDateTime(row.planned_end)}}</template></el-table-column>
        <el-table-column label="预计工时" width="95"><template #default="{row}">{{row.estimated_hours}}h</template></el-table-column>
        <el-table-column label="状态" width="95"><template #default="{row}"><el-tag :type="row.effective_status==='delayed'?'danger':row.effective_status==='completed'?'success':''" effect="plain">{{statusLabel[row.effective_status]}}</el-tag></template></el-table-column>
        <el-table-column label="操作" fixed="right" width="205"><template #default="{row}"><template v-if="canEditTask(row)"><el-button v-if="!row.parent_id&&canManageProject(projects.find(project=>project.id===row.project_id))" link @click="openCreate(row)">添加子任务</el-button><el-button link type="primary" @click="openEdit(row)">编辑</el-button><el-button v-if="['not_started','cancelled'].includes(row.status)&&!row.children?.length" link type="danger" @click="remove(row)">删除</el-button></template></template></el-table-column>
      </el-table>
      <div class="table-footer"><el-pagination v-model:current-page="query.page" v-model:page-size="query.page_size" :total="total" :page-sizes="[50,100,200]" layout="total, sizes, prev, pager, next" @change="load"/></div>
    </section>
    <el-dialog v-model="dialogVisible" :title="editingId?'编辑任务':'新增任务'" width="720px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <div class="form-grid">
          <el-form-item label="所属项目" prop="project_id"><el-select v-model="form.project_id" :disabled="Boolean(editingId)" filterable style="width:100%" @change="changeProject"><el-option v-for="item in approvedProjects" :key="item.id" :label="item.name" :value="item.id"/></el-select></el-form-item>
          <el-form-item label="父任务"><el-select v-model="form.parent_id" clearable :disabled="Boolean(editingId&&form.parent_id)" style="width:100%"><el-option v-for="item in parentOptions" :key="item.id" :label="item.name" :value="item.id"/></el-select></el-form-item>
          <el-form-item label="任务名称" prop="name"><el-input v-model="form.name"/></el-form-item>
          <el-form-item label="任务类型"><el-select v-model="form.task_type" style="width:100%"><el-option v-for="item in taskTypes" :key="item" :value="item"/></el-select></el-form-item>
          <el-form-item label="负责人" prop="owner_ids"><el-select v-model="form.owner_ids" multiple filterable collapse-tags collapse-tags-tooltip style="width:100%"><el-option v-for="item in ownerOptions" :key="item.id" :label="`${item.name} (${item.employee_no})`" :value="item.id"/></el-select></el-form-item>
          <el-form-item label="任务状态"><el-select v-model="form.status" style="width:100%"><el-option v-for="item in statuses" :key="item" :label="statusLabel[item]" :value="item"/></el-select></el-form-item>
          <el-form-item label="计划开始" prop="planned_start"><el-date-picker v-model="form.planned_start" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%"/></el-form-item>
          <el-form-item label="计划结束" prop="planned_end"><el-date-picker v-model="form.planned_end" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%"/></el-form-item>
          <el-form-item label="预计工时"><el-input-number v-model="form.estimated_hours" :min="0" :precision="1" style="width:100%"/></el-form-item>
        </div>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="3"/></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="2"/></el-form-item>
        <div class="form-hint">新增任务不再设置优先级；负责人支持多选，且必须是当前有效项目成员。</div>
      </el-form>
      <template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 18px}.task-name{font-weight:600;color:#39465a}.task-name.child{font-weight:400;color:#5f6b7c}.form-hint{margin-top:-4px;color:#9aa3b1;font-size:11px}
</style>
