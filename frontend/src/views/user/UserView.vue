<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createUser, deleteUser, getUsers, updateUser } from '@/api/user'
import { getDepartments, getOrganizationTree } from '@/api/organization'
import { getRoles } from '@/api/role'
import type { Department, OrganizationNode } from '@/types/organization'
import type { Role } from '@/types/role'
import type { EmployeeProfile, EmployeeProfilePayload, HRManagementLevel, User, UserPayload } from '@/types/user'
import { formatDateTime } from '@/utils/format'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const loading = ref(false)
const users = ref<User[]>([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 20, keyword: '', department_id: undefined as number | undefined, status: '' })
const departments = ref<Department[]>([])
const organizations = ref<OrganizationNode[]>([])
const roles = ref<Role[]>([])
const dialogVisible = ref(false)
const editingId = ref<number>()
const editingHrdbUser = ref(false)
const formRef = ref<FormInstance>()
type UserForm = Omit<UserPayload, 'employee_profile'> & { employee_profile: EmployeeProfilePayload }
const emptyProfile = (): EmployeeProfilePayload => ({ hr_management_level: 'employee' })
const editableProfile = (profile?: EmployeeProfile | null): EmployeeProfilePayload => ({
  position_id: profile?.position_id ?? null,
  employee_type: profile?.employee_type ?? null,
  local_f_name: profile?.local_f_name ?? null,
  english_f_name: profile?.english_f_name ?? null,
  local_g_name: profile?.local_g_name ?? null,
  english_g_name: profile?.english_g_name ?? null,
  preferred_name: profile?.preferred_name ?? null,
  gender: profile?.gender ?? null,
  job_id: profile?.job_id ?? null,
  job_title: profile?.job_title ?? null,
  eng_job_title: profile?.eng_job_title ?? null,
  chi_job_title: profile?.chi_job_title ?? null,
  degree: profile?.degree ?? null,
  staff_category: profile?.staff_category ?? null,
  site: profile?.site ?? null,
  cost_center_code: profile?.cost_center_code ?? null,
  personnel_area: profile?.personnel_area ?? null,
  personnel_sub_area: profile?.personnel_sub_area ?? null,
  hr_management_level: profile?.hr_management_level ?? 'employee',
})
const emptyForm = (): UserForm => ({
  employee_no: '',
  password: '',
  confirm_password: '',
  name: '',
  email: '',
  phone: '',
  department_id: null,
  organization_id: null,
  supervisor_id: null,
  status: 'active',
  role_ids: [],
  employee_profile: emptyProfile(),
})
const form = reactive<UserForm>(emptyForm())
const employeeNoPattern = /^(?=.*[A-Za-z0-9])[\x21-\x7E]+$/
const rules: FormRules = {
  employee_no: [
    { required: true, message: '请输入员工号', trigger: 'blur' },
    { min: 2, max: 50, message: '员工号长度应为 2–50 个字符', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value && !employeeNoPattern.test(value)) {
          return callback(new Error('员工号只能包含英文字母、数字和英文符号，不能包含中文或空格'))
        }
        callback()
      },
      trigger: ['blur', 'change'],
    },
  ],
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  password: [{
    validator: (_rule, value, callback) => {
      if (!editingId.value && !value) return callback(new Error('请输入初始密码'))
      if (value && value.length < 8) return callback(new Error('密码至少需要 8 个字符'))
      callback()
    },
    trigger: 'blur',
  }],
  confirm_password: [{
    validator: (_rule, value, callback) => {
      if (!editingId.value && !value) return callback(new Error('请再次输入初始密码'))
      if (form.password && value !== form.password) return callback(new Error('两次输入的密码不一致'))
      if (!form.password && value) return callback(new Error('请先填写新密码'))
      callback()
    },
    trigger: 'blur',
  }],
  email: [{ type: 'email', message: '请输入正确的邮箱地址', trigger: 'blur' }],
}

const flatOrganizations = computed(() => {
  const result: Array<OrganizationNode & { label: string }> = []
  const walk = (nodes: OrganizationNode[], prefix = '') => nodes.forEach((node) => {
    result.push({ ...node, label: `${prefix}${node.name}` })
    walk(node.children || [], `${prefix}　`)
  })
  walk(organizations.value)
  return result
})
const hrManagementLabel: Record<HRManagementLevel, string> = {
  employee: '普通员工',
  department_manager: 'Department Manager（人事职级）',
  management_manager: 'Management Manager（人事职级）',
}
const autoSystemRole = computed(() => {
  if (form.employee_profile.hr_management_level === 'department_manager') return 'L3（department_manager）'
  if (form.employee_profile.hr_management_level === 'management_manager') return 'L4（functional_manager）'
  return '无'
})
function roleLabel(code: string) {
  const systemRoleNames: Record<string, string> = {
    super_admin: '超级管理员',
    department_manager: 'L3',
    functional_manager: 'L4',
    project_manager: '项目经理',
    project_member: '项目成员',
  }
  return roles.value.find((item) => item.code === code)?.name || systemRoleNames[code] || code
}
function roleSource(row: User, code: string) {
  const manual = row.manual_roles?.includes(code)
  const hr = row.hr_roles?.includes(code)
  if (manual && hr) return '人工 + 职级'
  return hr ? '职级自动' : '人工'
}

async function load() {
  loading.value = true
  try {
    const result = await getUsers({ ...query, keyword: query.keyword || undefined, status: query.status || undefined })
    users.value = result.items
    total.value = result.total
  } finally { loading.value = false }
}

async function loadOptions() {
  const [departmentData, organizationData, roleData] = await Promise.all([
    getDepartments(),
    getOrganizationTree(),
    userStore.hasPermission('role:view') ? getRoles() : Promise.resolve([]),
  ])
  departments.value = departmentData
  organizations.value = organizationData
  roles.value = roleData
}

function openCreate() {
  editingId.value = undefined
  editingHrdbUser.value = false
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

function openEdit(row: User) {
  editingId.value = row.id
  editingHrdbUser.value = row.employee_profile?.data_source === 'hrdb'
  Object.assign(form, {
    employee_no: row.employee_no,
    password: '',
    confirm_password: '',
    name: row.name,
    email: row.email || '',
    phone: row.phone || '',
    department_id: row.department_id ?? null,
    organization_id: row.organization_id ?? null,
    supervisor_id: row.supervisor_id ?? null,
    status: row.status,
    role_ids: [...(row.manual_role_ids || row.role_ids)],
    employee_profile: editableProfile(row.employee_profile),
  })
  dialogVisible.value = true
}

function clearToNull() {
  return null
}

function handleDepartmentChange(departmentId: number | null | undefined) {
  form.department_id = departmentId ?? null
  if (
    form.organization_id
    && !flatOrganizations.value.some(
      (organization) => organization.id === form.organization_id && organization.department_id === form.department_id,
    )
  ) {
    form.organization_id = null
  }
}

async function save() {
  if (!editingId.value && form.employee_no) form.employee_no = form.employee_no.normalize('NFKC').trim()
  if (!(await formRef.value?.validate())) return
  const payload: Partial<UserPayload> = {
    ...form,
    department_id: form.department_id ?? null,
    organization_id: form.organization_id ?? null,
    supervisor_id: form.supervisor_id ?? null,
  }
  if (!payload.password) {
    delete payload.password
    delete payload.confirm_password
  }
  try {
    if (editingId.value) {
      delete payload.employee_no
      if (editingHrdbUser.value) {
        delete payload.name
        delete payload.email
        delete payload.phone
        delete payload.department_id
        delete payload.organization_id
        delete payload.supervisor_id
        delete payload.employee_profile
      }
      await updateUser(editingId.value, payload)
    } else {
      await createUser(payload as UserPayload)
    }
    ElMessage.success('用户信息已保存')
    dialogVisible.value = false
    await load()
  } catch {
    // 统一请求层已经显示后端返回的具体错误。
  }
}

async function toggleStatus(row: User) {
  const status = row.status === 'active' ? 'disabled' : 'active'
  await updateUser(row.id, { status })
  ElMessage.success(status === 'active' ? '用户已启用' : '用户已禁用')
  await load()
}

async function remove(row: User) {
  await ElMessageBox.confirm(
    `确认删除用户“${row.name}（${row.employee_no}）”吗？用户将无法登录，但历史业务记录会保留。`,
    '删除用户',
    { type: 'warning', confirmButtonText: '确认删除' },
  )
  await deleteUser(row.id)
  ElMessage.success('用户已删除')
  await load()
}

onMounted(async () => { await loadOptions(); await load() })
</script>

<template>
  <div class="page-shell">
    <header class="page-header"><div><h1 class="page-title">用户管理</h1><p class="page-subtitle">员工号用于登录；人事职级与系统权限角色分别维护，并按规则自动关联 L3/L4。</p></div><el-button v-if="userStore.hasPermission('user:edit')" type="primary" @click="openCreate">新增用户</el-button></header>
    <section class="surface filter-bar">
      <el-input v-model="query.keyword" clearable placeholder="姓名或员工号" style="width:220px" @keyup.enter="query.page=1;load()" />
      <el-select v-model="query.department_id" clearable placeholder="所属部门" style="width:180px"><el-option v-for="item in departments" :key="item.id" :label="item.name" :value="item.id" /></el-select>
      <el-select v-model="query.status" clearable placeholder="账号状态" style="width:140px"><el-option label="启用" value="active" /><el-option label="禁用" value="disabled" /></el-select>
      <el-button @click="query.page=1;load()">查询</el-button>
    </section>
    <section class="surface table-card">
      <el-table v-loading="loading" :data="users" stripe>
        <el-table-column prop="employee_no" label="员工号/登录账号" min-width="145" />
        <el-table-column prop="name" label="姓名" min-width="110" />
        <el-table-column label="岗位/人事职级" min-width="190"><template #default="{ row }"><div class="profile-cell"><strong>{{ row.employee_profile?.job_title || row.employee_profile?.position_id || '—' }}</strong><small>{{ hrManagementLabel[row.employee_profile?.hr_management_level || 'employee'] }}</small></div></template></el-table-column>
        <el-table-column prop="email" label="邮箱" min-width="190" show-overflow-tooltip />
        <el-table-column prop="department_name" label="部门" min-width="130" />
        <el-table-column prop="organization_name" label="组织" min-width="150" />
        <el-table-column prop="supervisor_name" label="直属主管" min-width="110" />
        <el-table-column label="系统角色" min-width="240"><template #default="{ row }"><el-tag v-for="role in row.roles" :key="role" size="small" :type="roleSource(row,role).includes('职级')?'warning':'info'" effect="plain" class="role-tag">{{ roleLabel(role) }} · {{ roleSource(row,role) }}</el-tag></template></el-table-column>
        <el-table-column label="状态" width="90"><template #default="{ row }"><span><i class="status-dot" :class="{active:row.status==='active'}"></i>{{ row.status==='active'?'启用':'禁用' }}</span></template></el-table-column>
        <el-table-column label="创建时间" width="155"><template #default="{ row }">{{ formatDateTime(row.created_at) }}</template></el-table-column>
        <el-table-column v-if="userStore.hasPermission('user:edit')" label="操作" fixed="right" width="205"><template #default="{ row }"><el-button link type="primary" @click="openEdit(row)">编辑</el-button><el-button link :type="row.status==='active'?'danger':'success'" @click="toggleStatus(row)">{{ row.status==='active'?'禁用':'启用' }}</el-button><el-button v-if="row.id!==userStore.profile?.id" link type="danger" @click="remove(row)">删除</el-button></template></el-table-column>
      </el-table>
      <div class="table-footer"><el-pagination v-model:current-page="query.page" v-model:page-size="query.page_size" :total="total" layout="total, sizes, prev, pager, next" @change="load" /></div>
    </section>

    <el-dialog v-model="dialogVisible" :title="editingId?'编辑用户':'新增用户'" width="860px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-tabs>
          <el-tab-pane label="账号与组织">
            <div class="form-grid">
              <el-form-item label="员工号（同时作为登录账号）" prop="employee_no"><el-input v-model.trim="form.employee_no" :disabled="Boolean(editingId)" placeholder="英文、数字或英文符号，不能含空格" /></el-form-item>
              <el-form-item :label="editingId?'重置密码（留空不修改）':'初始密码'" prop="password"><el-input v-model="form.password" type="password" show-password /></el-form-item>
              <el-form-item :label="editingId?'确认新密码':'确认初始密码'" prop="confirm_password"><el-input v-model="form.confirm_password" type="password" show-password /></el-form-item>
              <el-form-item label="姓名" prop="name"><el-input v-model="form.name" :disabled="editingHrdbUser" /></el-form-item>
              <el-form-item label="邮箱" prop="email"><el-input v-model="form.email" :disabled="editingHrdbUser" /></el-form-item>
              <el-form-item label="手机号"><el-input v-model="form.phone" :disabled="editingHrdbUser" /></el-form-item>
              <el-form-item label="账号状态"><el-select v-model="form.status" style="width:100%"><el-option label="启用" value="active" /><el-option label="禁用" value="disabled" /></el-select></el-form-item>
              <el-form-item label="所属部门"><el-select v-model="form.department_id" clearable :disabled="editingHrdbUser" :value-on-clear="clearToNull" style="width:100%" @change="handleDepartmentChange"><el-option v-for="item in departments" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
              <el-form-item label="所属组织"><el-select v-model="form.organization_id" clearable filterable :disabled="editingHrdbUser" :value-on-clear="clearToNull" style="width:100%"><el-option v-for="item in flatOrganizations.filter(v=>!form.department_id||v.department_id===form.department_id)" :key="item.id" :label="item.label" :value="item.id" /></el-select></el-form-item>
              <el-form-item label="直属主管"><el-select v-model="form.supervisor_id" clearable filterable :disabled="editingHrdbUser" :value-on-clear="clearToNull" style="width:100%"><el-option v-for="item in users.filter(v=>v.id!==editingId)" :key="item.id" :label="`${item.name} (${item.employee_no})`" :value="item.id" /></el-select></el-form-item>
              <el-form-item label="人工分配的系统角色"><el-select v-model="form.role_ids" multiple style="width:100%"><el-option v-for="item in roles" :key="item.id" :label="`${item.name}（${item.code}）`" :value="item.id" /></el-select></el-form-item>
            </div>
            <el-alert :title="editingHrdbUser?'该用户的人员与组织主数据来自 HRDB，只能维护账号状态、密码和人工系统角色。':'超级管理员、L3、L4、项目经理和项目成员仍是独立的系统权限角色；未选择角色时系统默认授予项目成员。'" type="info" :closable="false" show-icon/>
          </el-tab-pane>
          <el-tab-pane label="人员档案与职级">
            <el-alert :title="`当前人事职级将自动授予的系统角色：${autoSystemRole}`" type="warning" :closable="false" show-icon/>
            <fieldset class="profile-fieldset" :disabled="editingHrdbUser"><div class="form-grid profile-grid">
              <el-form-item label="人事管理职级"><el-select v-model="form.employee_profile.hr_management_level" style="width:100%"><el-option v-for="(label,value) in hrManagementLabel" :key="value" :label="label" :value="value" /></el-select></el-form-item>
              <el-form-item label="岗位编号"><el-input v-model="form.employee_profile.position_id" /></el-form-item>
              <el-form-item label="常用姓名"><el-input v-model="form.employee_profile.preferred_name" /></el-form-item>
              <el-form-item label="员工类型"><el-input v-model="form.employee_profile.employee_type" maxlength="1" /></el-form-item>
              <el-form-item label="本地姓"><el-input v-model="form.employee_profile.local_f_name" /></el-form-item>
              <el-form-item label="本地名"><el-input v-model="form.employee_profile.local_g_name" /></el-form-item>
              <el-form-item label="英文姓"><el-input v-model="form.employee_profile.english_f_name" /></el-form-item>
              <el-form-item label="英文名"><el-input v-model="form.employee_profile.english_g_name" /></el-form-item>
              <el-form-item label="职务编号"><el-input v-model="form.employee_profile.job_id" /></el-form-item>
              <el-form-item label="职务名称"><el-input v-model="form.employee_profile.job_title" /></el-form-item>
              <el-form-item label="中文职务"><el-input v-model="form.employee_profile.chi_job_title" /></el-form-item>
              <el-form-item label="英文职务"><el-input v-model="form.employee_profile.eng_job_title" /></el-form-item>
              <el-form-item label="员工类别"><el-input v-model="form.employee_profile.staff_category" maxlength="1" /></el-form-item>
              <el-form-item label="性别代码"><el-input v-model="form.employee_profile.gender" maxlength="1" /></el-form-item>
              <el-form-item label="学历"><el-input v-model="form.employee_profile.degree" /></el-form-item>
              <el-form-item label="工作地点"><el-input v-model="form.employee_profile.site" /></el-form-item>
              <el-form-item label="成本中心"><el-input v-model="form.employee_profile.cost_center_code" /></el-form-item>
              <el-form-item label="人事区域"><el-input v-model="form.employee_profile.personnel_area" /></el-form-item>
              <el-form-item label="人事子区域"><el-input v-model="form.employee_profile.personnel_sub_area" /></el-form-item>
            </div></fieldset>
          </el-tab-pane>
        </el-tabs>
      </el-form>
      <template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.role-tag { margin: 2px 5px 2px 0; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 18px; }
.profile-grid{max-height:470px;overflow-y:auto;margin-top:16px;padding-right:8px}.profile-cell{display:flex;flex-direction:column}.profile-cell strong{color:#445064;font-size:12px}.profile-cell small{margin-top:3px;color:#8c96a5;font-size:10px}
.profile-fieldset{margin:0;border:0;padding:0}.profile-fieldset:disabled{opacity:.65}
</style>
