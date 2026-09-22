<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  approveProject,
  createProject,
  completeProject,
  deleteProject,
  getAllProjects,
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
const projectOptions = ref<Project[]>([])
const total = ref(0)
const users = ref<UserOption[]>([])
const departments = ref<DepartmentOption[]>([])
const organizations = ref<OrganizationNode[]>([])
const filterScope = ref('')
const query = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
  status: '',
  manager_id: undefined as number | undefined,
  department_id: undefined as number | undefined,
  organization_id: undefined as number | undefined,
})
const dialogVisible = ref(false)
const editingId = ref<number>()
const editingProject = ref<Project>()
const formRef = ref<FormInstance>()
const privileged = computed(() => (userStore.profile?.roles || []).some(role => ['super_admin', 'department_manager'].includes(role)))
const canCreateProject = computed(() => userStore.hasPermission('project:edit') && (privileged.value || userStore.profile?.roles.includes('project_manager') || userStore.profile?.roles.includes('functional_manager')))
const canManageProject = (project: Project) => project.can_manage
const projectManagerOptions = computed(() => {
  const managerIds = new Set(projectOptions.value.map((item) => item.manager_id))
  return users.value.filter((item) => managerIds.has(item.id))
})
const emptyForm = (): ProjectPayload => ({
  name: '',
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
const statuses = ['not_started', 'running', 'completed', 'delayed']
const statusLabel: Record<string, string> = {
  not_started: '未开始',
  running: '进行中',
  completed: '已完成',
  delayed: '已逾期',
}
const approvalLabel = { draft: '草稿', pending: '待部门主管审批', approved: '已审批', rejected: '已驳回' }
const approvalType = { draft: 'info', pending: 'warning', approved: 'success', rejected: 'danger' } as const
const statusTypeMap: Record<string, 'primary' | 'success' | 'warning' | 'danger' | 'info'> = {
  running: 'primary',
  completed: 'success',
  delayed: 'danger',
}
const statusType = (status: string) => statusTypeMap[status] || 'info'
const canReview = (row: Project) =>
  row.approval_status === 'pending'
  && row.approver_id === userStore.profile?.id
  && Boolean(userStore.profile?.roles.includes('department_manager'))

interface MemberCascaderOption {
  value: string | number
  label: string
  children?: MemberCascaderOption[]
}

const filterCascaderProps = { checkStrictly: true, emitPath: false }

function managerFilterOrganizationOption(node: OrganizationNode): MemberCascaderOption | undefined {
  if (node.status !== 'active') return undefined
  const childOrganizations = (node.children || [])
    .map(managerFilterOrganizationOption)
    .filter((item): item is MemberCascaderOption => Boolean(item))
  const managerOptions = projectManagerOptions.value
    .filter((item) => item.organization_id === node.id)
    .map((item) => ({
      value: `user:${item.id}`,
      label: `${item.name}（${item.employee_no}）`,
    }))
  const children = [...childOrganizations, ...managerOptions]
  return {
    value: `organization:${node.id}`,
    label: node.name,
    ...(children.length ? { children } : {}),
  }
}

const filterCascaderOptions = computed<MemberCascaderOption[]>(() =>
  departments.value.map((department) => {
    const organizationChildren = organizations.value
      .filter((node) => node.department_id === department.id)
      .map(managerFilterOrganizationOption)
      .filter((item): item is MemberCascaderOption => Boolean(item))
    const unassignedManagers = projectManagerOptions.value
      .filter((item) => item.department_id === department.id && !item.organization_id)
      .map((item) => ({
        value: `user:${item.id}`,
        label: `${item.name}（${item.employee_no}）`,
      }))
    const children = [...organizationChildren, ...unassignedManagers]
    return {
      value: `department:${department.id}`,
      label: department.name,
      ...(children.length ? { children } : {}),
    }
  }),
)

function syncFilterScope() {
  query.manager_id = undefined
  query.department_id = undefined
  query.organization_id = undefined
  if (!filterScope.value) return
  const [kind, rawId] = filterScope.value.split(':')
  const id = Number(rawId)
  if (kind === 'department') query.department_id = id
  if (kind === 'organization') query.organization_id = id
  if (kind === 'user') query.manager_id = id
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
        && item.id !== form.manager_id,
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
            && item.id !== form.manager_id,
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
    })
    projects.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

async function loadOptions() {
  const [departmentOptions, organizationTree, userOptions, allProjects] = await Promise.all([
    getDepartmentOptions(),
    getOrganizationTree(),
    getUserOptions(),
    getAllProjects(),
  ])
  departments.value = departmentOptions
  organizations.value = organizationTree
  users.value = userOptions
  projectOptions.value = allProjects
}

async function applyFilters() {
  syncFilterScope()
  query.page = 1
  await load()
}

function openCreate() {
  editingId.value = undefined
  editingProject.value = undefined
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

function changeManager(managerId: number) {
  const manager = users.value.find((item) => item.id === managerId)
  if (manager?.department_id) form.department_id = manager.department_id
  form.member_ids = form.member_ids.filter((id) => id !== managerId)
}

function openEdit(row: Project) {
  editingId.value = row.id
  editingProject.value = row
  Object.assign(form, {
    name: row.name,
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
    ElMessage.success('项目已提交部门主管审批')
  } else ElMessage.success(editingId.value ? '项目已保存' : '项目草稿已保存')
  dialogVisible.value = false
  await load()
}

async function submitExisting(row: Project) {
  await ElMessageBox.confirm(`确认提交项目“${row.name}”审批吗？`, '提交项目', { type: 'warning' })
  await submitProject(row.id)
  ElMessage.success('项目已提交部门主管审批')
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

async function finish(row: Project) {
  await ElMessageBox.confirm(`项目“${row.name}”的全部任务已完成。确认正式结束项目吗？确认后不能再新增任务。`, '确认项目完成', { type: 'warning', confirmButtonText: '确认完成' })
  await completeProject(row.id)
  ElMessage.success('项目已正式完成')
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
        <p class="page-subtitle">展示权限范围内的项目；项目负责人维护自己的项目，超级管理员与部门主管可管理全部项目。</p>
      </div>
      <el-button v-if="canCreateProject" type="primary" @click="openCreate">新建项目</el-button>
    </header>
    <el-alert
      v-if="userStore.hasPermission('project:edit') && !canCreateProject"
      title="作为成员参与的项目可以查看；项目维护由项目负责人、超级管理员或部门主管操作。"
      type="info"
      :closable="false"
      show-icon
    />
    <section class="surface filter-bar">
      <el-select v-model="query.keyword" clearable filterable allow-create default-first-option placeholder="项目编号或名称" style="width:240px" @keyup.enter="applyFilters">
        <el-option v-for="item in projectOptions" :key="item.id" :label="`${item.code} · ${item.name}`" :value="item.code"/>
      </el-select>
      <el-select v-model="query.status" clearable placeholder="项目状态" style="width:150px">
        <el-option v-for="item in statuses" :key="item" :label="statusLabel[item]" :value="item"/>
      </el-select>
      <el-cascader v-model="filterScope" :options="filterCascaderOptions" :props="filterCascaderProps" clearable filterable placeholder="部门 / 组织 / 项目经理" style="width:280px" @change="syncFilterScope"/>
      <el-button @click="applyFilters">查询</el-button>
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
            <el-tag :type="statusType(row.effective_status)" effect="light">{{ statusLabel[row.effective_status] }}</el-tag>
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
              <el-button v-if="['draft','rejected'].includes(row.approval_status)&&canManageProject(row)" link type="warning" @click="submitExisting(row)">提交审批</el-button>
              <el-button
                v-if="row.status!=='completed' && row.approval_status!=='pending' && canManageProject(row)"
                link
                type="primary"
                @click="openEdit(row)"
              >编辑</el-button>
              <el-button v-if="['draft','rejected'].includes(row.approval_status) && canManageProject(row)" link type="danger" @click="remove(row)">删除</el-button>
              <el-button v-if="row.all_tasks_completed && row.approval_status==='approved' && row.status!=='completed' && canManageProject(row)" link type="success" @click="finish(row)">确认完成</el-button>
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
        title="项目编号由系统自动生成；请指定项目成员，所有项目提交后均由项目所属部门的部门主管审批。"
        type="info"
        :closable="false"
        show-icon
      />
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <div class="form-grid">
          <el-form-item label="项目编号"><el-input model-value="保存后由系统自动生成" disabled/></el-form-item>
          <el-form-item label="项目名称" prop="name"><el-input v-model="form.name"/></el-form-item>
          <el-form-item label="项目经理" prop="manager_id">
            <el-select v-model="form.manager_id" filterable :disabled="Boolean(editingId) || !privileged" style="width:100%" @change="changeManager">
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
