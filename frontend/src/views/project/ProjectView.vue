<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  approveProject,
  createProject,
  deleteProject,
  getProjects,
  rejectProject,
  submitProject,
  updateProject,
} from '@/api/project'
import { getDepartmentOptions, getOrganizationTree } from '@/api/organization'
import { getUserOptions } from '@/api/user'
import type { DepartmentOption, OrganizationNode } from '@/types/organization'
import type { Project, ProjectPayload } from '@/types/project'
import type { UserOption } from '@/types/user'
import { formatDate } from '@/utils/format'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const loading = ref(false)
const projects = ref<Project[]>([])
const total = ref(0)
const users = ref<UserOption[]>([])
const departments = ref<DepartmentOption[]>([])
const organizations = ref<OrganizationNode[]>([])
const query = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
  status: '',
  manager_id: undefined as number | undefined,
  department_id: undefined as number | undefined,
  organization_id: undefined as number | undefined,
  employee_no: '',
  name: '',
})
const dialogVisible = ref(false)
const editingId = ref<number>()
const editingProject = ref<Project>()
const formRef = ref<FormInstance>()
const isProjectManager = computed(() => userStore.profile?.roles.includes('project_manager') || false)
const canCreateProject = computed(() => isProjectManager.value)
const canManageProject = (project: Project) => {
  const roles = userStore.profile?.roles || []
  return project.manager_id === userStore.profile?.id && roles.includes('project_manager')
}
const emptyForm = (): ProjectPayload => ({
  name: '',
  project_type: 'General',
  manager_id: userStore.profile?.id || 0,
  member_ids: [],
  department_id: userStore.profile?.department_id || 0,
  budget_hours: 8,
  planned_start: '',
  planned_end: '',
  description: '',
  remark: '',
})
const form = reactive<ProjectPayload>(emptyForm())
const rules: FormRules = {
  name: [{ required: true, message: '请输入项目名称' }],
  manager_id: [{ required: true, message: '请选择项目经理' }],
  member_ids: [{ required: true, type: 'array', min: 1, message: '请至少选择一名项目成员' }],
  department_id: [{ required: true, message: '请选择所属部门' }],
  budget_hours: [{ required: true, message: '请输入项目总工时' }],
  planned_start: [{ required: true, message: '请选择计划开始日期' }],
  planned_end: [{ required: true, message: '请选择计划结束日期' }],
}
const statuses = ['Draft', 'Planned', 'Running', 'Suspended', 'Completed', 'Cancelled']
const statusLabel: Record<string, string> = {
  Draft: '草稿',
  Planned: '已计划',
  Running: '进行中',
  Suspended: '暂停',
  Completed: '已完成',
  Cancelled: '已取消',
}
const approvalLabel = { draft: '草稿', pending: '待直属主管审批', approved: '已审批', rejected: '已驳回' }
const approvalType = { draft: 'info', pending: 'warning', approved: 'success', rejected: 'danger' } as const
const flatOrganizations = computed(() => {
  const result: Array<OrganizationNode & { label: string }> = []
  const walk = (nodes: OrganizationNode[], prefix = '') => nodes.forEach((node) => {
    result.push({ ...node, label: `${prefix}${node.name}` })
    walk(node.children || [], `${prefix}　`)
  })
  walk(organizations.value)
  return result
})
const statusTypeMap: Record<string, 'primary' | 'success' | 'warning' | 'info'> = {
  Running: 'primary',
  Completed: 'success',
  Suspended: 'warning',
  Cancelled: 'info',
}
const statusType = (status: string) => statusTypeMap[status] || ''
const canReview = (row: Project) =>
  row.approval_status === 'pending'
  && row.approver_id === userStore.profile?.id

interface MemberCascaderOption {
  value: string | number
  label: string
  children?: MemberCascaderOption[]
}

const memberCascaderProps = {
  multiple: true,
  emitPath: false,
}

function organizationMemberOption(node: OrganizationNode): MemberCascaderOption | undefined {
  if (node.status !== 'active') return undefined
  const childOrganizations = (node.children || [])
    .map(organizationMemberOption)
    .filter((item): item is MemberCascaderOption => Boolean(item))
  const memberOptions = users.value
    .filter(
      (item) =>
        item.organization_id === node.id
        && item.id !== userStore.profile?.id,
    )
    .map((item) => ({
      value: item.id,
      label: `${item.name} (${item.employee_no})`,
    }))
  const children = [...childOrganizations, ...memberOptions]
  if (!children.length) return undefined
  return {
    value: `organization-${node.id}`,
    label: node.name,
    children,
  }
}

const memberCascaderOptions = computed<MemberCascaderOption[]>(() =>
  departments.value
    .map((department) => {
      const organizationChildren = organizations.value
        .filter((node) => node.department_id === department.id)
        .map(organizationMemberOption)
        .filter((item): item is MemberCascaderOption => Boolean(item))
      const unassignedMembers = users.value
        .filter(
          (item) =>
            item.department_id === department.id
            && !item.organization_id
            && item.id !== userStore.profile?.id,
        )
        .map((item) => ({
          value: item.id,
          label: `${item.name} (${item.employee_no})`,
        }))
      const children = [
        ...organizationChildren,
        ...unassignedMembers,
      ]
      return {
        value: `department-${department.id}`,
        label: department.name,
        children,
      }
    })
    .filter((item) => item.children.length),
)

async function load() {
  loading.value = true
  try {
    const result = await getProjects({
      ...query,
      keyword: query.keyword || undefined,
      status: query.status || undefined,
      employee_no: query.employee_no || undefined,
      name: query.name || undefined,
    })
    projects.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

async function loadOptions() {
  const [departmentOptions, organizationTree, userOptions] = await Promise.all([
    getDepartmentOptions(),
    getOrganizationTree(),
    userStore.hasPermission('project:edit') ? getUserOptions() : Promise.resolve([]),
  ])
  departments.value = departmentOptions
  organizations.value = organizationTree
  users.value = userOptions
}

function openCreate() {
  editingId.value = undefined
  editingProject.value = undefined
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

function openEdit(row: Project) {
  editingId.value = row.id
  editingProject.value = row
  Object.assign(form, {
    name: row.name,
    project_type: row.project_type,
    manager_id: row.manager_id,
    member_ids: [],
    department_id: row.department_id,
    budget_hours: row.budget_hours,
    planned_start: row.planned_start,
    planned_end: row.planned_end,
    description: row.description || '',
    remark: row.remark || '',
  })
  dialogVisible.value = true
}

async function save(submitAfterSave = false) {
  if (!(await formRef.value?.validate())) return
  if (form.planned_end < form.planned_start) {
    return ElMessage.warning('计划结束日期不能早于开始日期')
  }
  let saved: Project
  if (editingId.value) {
    const { member_ids: _memberIds, ...payload } = form
    if (editingProject.value?.approval_status === 'approved') {
      const {
        manager_id: _managerId,
        department_id: _departmentId,
        budget_hours: _budgetHours,
        ...editable
      } = payload
      saved = await updateProject(editingId.value, editable)
    } else {
      saved = await updateProject(editingId.value, payload)
    }
  } else {
    saved = await createProject(form)
  }
  if (submitAfterSave && saved.approval_status !== 'approved') {
    await submitProject(saved.id)
    ElMessage.success('项目已提交直属主管审批')
  } else ElMessage.success(saved.approval_status === 'approved' ? '项目已自动审批通过' : '项目草稿已保存')
  dialogVisible.value = false
  await load()
}

async function submitExisting(row: Project) {
  await ElMessageBox.confirm(`确认提交项目“${row.name}”审批吗？`, '提交项目', { type: 'warning' })
  await submitProject(row.id)
  ElMessage.success('项目已提交直属主管审批')
  await load()
}

async function approve(row: Project) {
  await ElMessageBox.confirm(
    `确认批准项目“${row.name}”及 ${row.budget_hours} 小时工时额度吗？`,
    '项目审批',
    { type: 'warning' },
  )
  await approveProject(row.id)
  ElMessage.success('项目已批准')
  await load()
}

async function reject(row: Project) {
  const { value } = await ElMessageBox.prompt('请输入驳回原因', '项目审批', {
    inputType: 'textarea',
    inputValidator: (value) => Boolean(value?.trim()) || '请填写驳回原因',
  })
  await rejectProject(row.id, value)
  ElMessage.success('项目已驳回')
  await load()
}

async function remove(row: Project) {
  await ElMessageBox.confirm(`确认删除未审批项目“${row.name}”吗？`, '删除项目', {
    type: 'warning',
  })
  await deleteProject(row.id)
  ElMessage.success('项目已删除')
  await load()
}

onMounted(async () => {
  await loadOptions()
  await load()
})
</script>

<template>
  <div class="page-shell">
    <header class="page-header">
      <div>
        <h1 class="page-title">项目管理</h1>
        <p class="page-subtitle">仅展示当前用户作为项目经理负责的项目，并由项目经理维护项目与成员。</p>
      </div>
      <el-button v-if="canCreateProject" type="primary" @click="openCreate">新建项目</el-button>
    </header>
    <el-alert
      v-if="userStore.hasPermission('project:edit') && !canCreateProject"
      title="只有项目经理可以创建和维护自己负责的项目。"
      type="info"
      :closable="false"
      show-icon
    />
    <section class="surface filter-bar">
      <el-input v-model="query.keyword" clearable placeholder="项目编号或名称" style="width:220px" @keyup.enter="query.page=1;load()"/>
      <el-select v-model="query.status" clearable placeholder="项目状态" style="width:150px">
        <el-option v-for="item in statuses" :key="item" :label="statusLabel[item]" :value="item"/>
      </el-select>
      <el-select v-if="userStore.hasPermission('project:edit')" v-model="query.manager_id" clearable filterable placeholder="项目经理" style="width:160px">
        <el-option v-for="item in users" :key="item.id" :label="item.name" :value="item.id"/>
      </el-select>
      <el-select v-model="query.department_id" clearable placeholder="所属部门" style="width:160px">
        <el-option v-for="item in departments" :key="item.id" :label="item.name" :value="item.id"/>
      </el-select>
      <el-select v-model="query.organization_id" clearable filterable placeholder="成员组织" style="width:180px"><el-option v-for="item in flatOrganizations" :key="item.id" :label="item.label" :value="item.id"/></el-select>
      <el-input v-model="query.employee_no" clearable placeholder="成员工号" style="width:150px"/>
      <el-input v-model="query.name" clearable placeholder="成员姓名" style="width:150px"/>
      <el-button @click="query.page=1;load()">查询</el-button>
    </section>
    <section class="surface table-card">
      <el-table v-loading="loading" :data="projects" stripe>
        <el-table-column prop="code" label="项目编号" width="130"/>
        <el-table-column label="项目名称" min-width="180">
          <template #default="{row}">
            <el-button link type="primary" @click="$router.push(`/projects/${row.id}`)">{{ row.name }}</el-button>
          </template>
        </el-table-column>
        <el-table-column prop="manager_name" label="项目经理" width="110"/>
        <el-table-column prop="manager_employee_no" label="工号" width="110"/>
        <el-table-column prop="manager_organization_name" label="组织" min-width="120"/>
        <el-table-column prop="department_name" label="部门" min-width="120"/>
        <el-table-column label="审批" width="115">
          <template #default="{row}">
            <el-tag :type="approvalType[row.approval_status]">{{ approvalLabel[row.approval_status] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="项目工时" width="150">
          <template #default="{row}">{{ row.booked_hours }} / {{ row.budget_hours }}h</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{row}">
            <el-tag :type="statusType(row.status)" effect="light">{{ statusLabel[row.status] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="计划周期" width="205">
          <template #default="{row}">{{ formatDate(row.planned_start) }} 至 {{ formatDate(row.planned_end) }}</template>
        </el-table-column>
        <el-table-column label="操作" fixed="right" width="220">
          <template #default="{row}">
            <el-button v-if="canReview(row)" link type="success" @click="approve(row)">批准</el-button>
            <el-button v-if="canReview(row)" link type="danger" @click="reject(row)">驳回</el-button>
            <template v-if="userStore.hasPermission('project:edit')">
              <el-button v-if="['draft','rejected'].includes(row.approval_status)&&row.manager_id===userStore.profile?.id" link type="warning" @click="submitExisting(row)">提交审批</el-button>
              <el-button
                v-if="!['Completed','Cancelled'].includes(row.status) && row.approval_status!=='pending' && canManageProject(row) && (row.approval_status==='approved' || row.manager_id===userStore.profile?.id)"
                link
                type="primary"
                @click="openEdit(row)"
              >编辑</el-button>
              <el-button v-if="['draft','rejected'].includes(row.approval_status) && row.manager_id===userStore.profile?.id" link type="danger" @click="remove(row)">删除</el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>
      <div class="table-footer">
        <el-pagination v-model:current-page="query.page" v-model:page-size="query.page_size" :total="total" layout="total, sizes, prev, pager, next" @change="load"/>
      </div>
    </section>

    <el-dialog v-model="dialogVisible" :title="editingId?'编辑项目':'新建项目'" width="720px" destroy-on-close>
      <el-alert
        v-if="!editingId"
        title="项目编号由系统自动生成；请指定项目成员，提交后由直属主管审批。"
        type="info"
        :closable="false"
        show-icon
      />
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <div class="form-grid">
          <el-form-item label="项目编号"><el-input model-value="保存后由系统自动生成" disabled/></el-form-item>
          <el-form-item label="项目名称" prop="name"><el-input v-model="form.name"/></el-form-item>
          <el-form-item label="项目类型"><el-input v-model="form.project_type"/></el-form-item>
          <el-form-item label="项目经理" prop="manager_id">
            <el-select v-model="form.manager_id" filterable disabled style="width:100%">
              <el-option v-for="item in users" :key="item.id" :label="item.name" :value="item.id"/>
            </el-select>
          </el-form-item>
          <el-form-item v-if="!editingId" label="初始项目成员" prop="member_ids">
            <el-cascader
              v-model="form.member_ids"
              :options="memberCascaderOptions"
              :props="memberCascaderProps"
              clearable
              collapse-tags
              collapse-tags-tooltip
              filterable
              placeholder="按部门 / 组织选择至少一名成员"
              style="width:100%"
            />
          </el-form-item>
          <el-form-item label="所属部门" prop="department_id">
            <el-select v-model="form.department_id" :disabled="editingProject?.approval_status==='approved'" style="width:100%">
              <el-option v-for="item in departments" :key="item.id" :label="item.name" :value="item.id"/>
            </el-select>
          </el-form-item>
          <el-form-item label="项目总工时" prop="budget_hours">
            <el-input-number v-model="form.budget_hours" :min="0.5" :step="0.5" :precision="2" :disabled="editingProject?.approval_status==='approved'" style="width:100%"/>
          </el-form-item>
          <el-form-item label="计划开始" prop="planned_start"><el-date-picker v-model="form.planned_start" value-format="YYYY-MM-DD" type="date" style="width:100%"/></el-form-item>
          <el-form-item label="计划结束" prop="planned_end"><el-date-picker v-model="form.planned_end" value-format="YYYY-MM-DD" type="date" style="width:100%"/></el-form-item>
        </div>
        <div class="field-hint">项目实际起止日期由任务执行记录自动汇总，无需手工填写。</div>
        <el-form-item label="项目描述"><el-input v-model="form.description" type="textarea" :rows="3"/></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="2"/></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible=false">取消</el-button>
        <el-button @click="save(false)">{{ editingProject?.approval_status==='approved' ? '保存' : '保存草稿' }}</el-button>
        <el-button v-if="editingProject?.approval_status!=='approved'" type="primary" @click="save(true)">保存并提交审批</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 18px}
.field-hint{margin:-2px 0 18px;color:var(--el-text-color-secondary);font-size:12px}
</style>
