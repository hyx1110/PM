<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createUser, deleteUser, getUsers, updateUser } from '@/api/user'
import { getDepartments, getOrganizationTree } from '@/api/organization'
import { getRoles } from '@/api/role'
import type { Department, OrganizationNode } from '@/types/organization'
import type { Role } from '@/types/role'
import type { User, UserPayload } from '@/types/user'
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
const formRef = ref<FormInstance>()
const emptyForm = (): UserPayload => ({
  username: '',
  password: '',
  name: '',
  email: '',
  phone: '',
  department_id: null,
  organization_id: null,
  supervisor_id: null,
  status: 'active',
  role_ids: [],
})
const form = reactive<UserPayload>(emptyForm())
const usernamePattern = /^(?=.*[A-Za-z0-9])[\x21-\x7E]+$/
const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '用户名长度应为 2–50 个字符', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value && !usernamePattern.test(value)) {
          return callback(new Error('用户名只能包含英文字母、数字和英文符号，不能包含中文或空格'))
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
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

function openEdit(row: User) {
  editingId.value = row.id
  Object.assign(form, {
    username: row.username,
    password: '',
    name: row.name,
    email: row.email || '',
    phone: row.phone || '',
    department_id: row.department_id ?? null,
    organization_id: row.organization_id ?? null,
    supervisor_id: row.supervisor_id ?? null,
    status: row.status,
    role_ids: [...row.role_ids],
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
  if (!editingId.value && form.username) form.username = form.username.normalize('NFKC').trim()
  if (!(await formRef.value?.validate())) return
  const payload = {
    ...form,
    department_id: form.department_id ?? null,
    organization_id: form.organization_id ?? null,
    supervisor_id: form.supervisor_id ?? null,
  }
  if (!payload.password) delete payload.password
  try {
    if (editingId.value) {
      delete payload.username
      await updateUser(editingId.value, payload)
    } else {
      await createUser(payload)
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
    `确认删除用户“${row.name}（${row.username}）”吗？用户将无法登录，但历史业务记录会保留。`,
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
    <header class="page-header"><div><h1 class="page-title">用户管理</h1><p class="page-subtitle">维护账号、组织归属、直属主管与系统角色。</p></div><el-button v-if="userStore.hasPermission('user:edit')" type="primary" @click="openCreate">新增用户</el-button></header>
    <section class="surface filter-bar">
      <el-input v-model="query.keyword" clearable placeholder="姓名或用户名" style="width:220px" @keyup.enter="query.page=1;load()" />
      <el-select v-model="query.department_id" clearable placeholder="所属部门" style="width:180px"><el-option v-for="item in departments" :key="item.id" :label="item.name" :value="item.id" /></el-select>
      <el-select v-model="query.status" clearable placeholder="账号状态" style="width:140px"><el-option label="启用" value="active" /><el-option label="禁用" value="disabled" /></el-select>
      <el-button @click="query.page=1;load()">查询</el-button>
    </section>
    <section class="surface table-card">
      <el-table v-loading="loading" :data="users" stripe>
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column prop="name" label="姓名" min-width="110" />
        <el-table-column prop="email" label="邮箱" min-width="190" show-overflow-tooltip />
        <el-table-column prop="department_name" label="部门" min-width="130" />
        <el-table-column prop="organization_name" label="组织" min-width="150" />
        <el-table-column prop="supervisor_name" label="直属主管" min-width="110" />
        <el-table-column label="角色" min-width="190"><template #default="{ row }"><el-tag v-for="role in row.roles" :key="role" size="small" effect="plain" class="role-tag">{{ role }}</el-tag></template></el-table-column>
        <el-table-column label="状态" width="90"><template #default="{ row }"><span><i class="status-dot" :class="{active:row.status==='active'}"></i>{{ row.status==='active'?'启用':'禁用' }}</span></template></el-table-column>
        <el-table-column label="创建时间" width="155"><template #default="{ row }">{{ formatDateTime(row.created_at) }}</template></el-table-column>
        <el-table-column v-if="userStore.hasPermission('user:edit')" label="操作" fixed="right" width="205"><template #default="{ row }"><el-button link type="primary" @click="openEdit(row)">编辑</el-button><el-button link :type="row.status==='active'?'danger':'success'" @click="toggleStatus(row)">{{ row.status==='active'?'禁用':'启用' }}</el-button><el-button v-if="row.id!==userStore.profile?.id" link type="danger" @click="remove(row)">删除</el-button></template></el-table-column>
      </el-table>
      <div class="table-footer"><el-pagination v-model:current-page="query.page" v-model:page-size="query.page_size" :total="total" layout="total, sizes, prev, pager, next" @change="load" /></div>
    </section>

    <el-dialog v-model="dialogVisible" :title="editingId?'编辑用户':'新增用户'" width="620px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <div class="form-grid">
          <el-form-item label="用户名" prop="username"><el-input v-model.trim="form.username" :disabled="Boolean(editingId)" placeholder="英文、数字或英文符号，不能含空格" /></el-form-item>
          <el-form-item :label="editingId?'重置密码（留空不修改）':'初始密码'" prop="password"><el-input v-model="form.password" type="password" show-password /></el-form-item>
          <el-form-item label="姓名" prop="name"><el-input v-model="form.name" /></el-form-item>
          <el-form-item label="邮箱" prop="email"><el-input v-model="form.email" /></el-form-item>
          <el-form-item label="手机号"><el-input v-model="form.phone" /></el-form-item>
          <el-form-item label="状态"><el-select v-model="form.status" style="width:100%"><el-option label="启用" value="active" /><el-option label="禁用" value="disabled" /></el-select></el-form-item>
          <el-form-item label="所属部门"><el-select v-model="form.department_id" clearable :value-on-clear="clearToNull" style="width:100%" @change="handleDepartmentChange"><el-option v-for="item in departments" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
          <el-form-item label="所属组织"><el-select v-model="form.organization_id" clearable filterable :value-on-clear="clearToNull" style="width:100%"><el-option v-for="item in flatOrganizations.filter(v=>!form.department_id||v.department_id===form.department_id)" :key="item.id" :label="item.label" :value="item.id" /></el-select></el-form-item>
          <el-form-item label="直属主管"><el-select v-model="form.supervisor_id" clearable filterable :value-on-clear="clearToNull" style="width:100%"><el-option v-for="item in users.filter(v=>v.id!==editingId)" :key="item.id" :label="`${item.name} (${item.username})`" :value="item.id" /></el-select></el-form-item>
          <el-form-item label="系统角色"><el-select v-model="form.role_ids" multiple style="width:100%"><el-option v-for="item in roles" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
        </div>
      </el-form>
      <template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.role-tag { margin: 2px 5px 2px 0; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 18px; }
</style>
