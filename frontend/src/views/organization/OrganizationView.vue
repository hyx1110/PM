<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createDepartment,
  createOrganization,
  deleteDepartment,
  deleteOrganization,
  getDepartments,
  getOrganizationTree,
  updateDepartment,
  updateOrganization,
} from '@/api/organization'
import { getL3UserOptions, getUserOptions } from '@/api/user'
import type { Department, OrganizationNode } from '@/types/organization'
import type { UserOption } from '@/types/user'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const loading = ref(false)
const departments = ref<Department[]>([])
const users = ref<UserOption[]>([])
const l3Users = ref<UserOption[]>([])
const tree = ref<OrganizationNode[]>([])
const activeDepartment = ref<number>()
const departmentDialog = ref(false)
const organizationDialog = ref(false)
const departmentId = ref<number>()
const organizationId = ref<number>()
const departmentForm = reactive({ code: '', name: '', manager_id: null as number | null, status: 'active' })
const organizationForm = reactive({ department_id: 0, parent_id: null as number | null, code: '', name: '', level: 'L1' as OrganizationNode['level'], manager_id: null as number | null, status: 'active' })
const rules: FormRules = { code: [{ required: true, message: '请输入编码' }], name: [{ required: true, message: '请输入名称' }] }
const formRef = ref<FormInstance>()
type DisplayNode = (Omit<OrganizationNode, 'children'> & { node_type: 'organization'; children: DisplayNode[] }) | {
  id: string; node_type: 'user_group' | 'user'; name: string; employee_no?: string; status?: string; children: DisplayNode[]
}
function organizationDisplayNode(node: OrganizationNode): DisplayNode {
  return {
    ...node,
    node_type: 'organization',
    children: [
      ...(node.children || []).map(organizationDisplayNode),
      ...(node.users || []).map((user) => ({
        id: `user-${user.id}`, node_type: 'user' as const, name: user.name,
        employee_no: user.employee_no, status: user.status, children: [],
      })),
    ],
  }
}
const displayTree = computed<DisplayNode[]>(() => {
  const result = tree.value.map(organizationDisplayNode)
  const unassigned = users.value.filter(
    (item) => item.department_id === activeDepartment.value && !item.organization_id,
  )
  if (unassigned.length) {
    result.push({
      id: `unassigned-${activeDepartment.value}`,
      node_type: 'user_group',
      name: '未分配组织',
      children: unassigned.map((user) => ({
        id: `unassigned-user-${user.id}`, node_type: 'user', name: user.name,
        employee_no: user.employee_no, children: [],
      })),
    })
  }
  return result
})

async function load() {
  loading.value = true
  try {
    departments.value = await getDepartments()
    if (!departments.value.some((item) => item.id === activeDepartment.value)) {
      activeDepartment.value = departments.value[0]?.id
    }
    tree.value = await getOrganizationTree(activeDepartment.value)
    ;[users.value, l3Users.value] = await Promise.all([
      getUserOptions(),
      getL3UserOptions(),
    ])
  } finally { loading.value = false }
}

async function switchDepartment(id: number) {
  activeDepartment.value = id
  tree.value = await getOrganizationTree(id)
}

function editDepartment(item?: Department) {
  departmentId.value = item?.id
  Object.assign(departmentForm, item ? { code: item.code, name: item.name, manager_id: item.manager_id ?? null, status: item.status } : { code: '', name: '', manager_id: null, status: 'active' })
  departmentDialog.value = true
}

async function saveDepartment() {
  if (!(await formRef.value?.validate())) return
  if (departmentId.value) await updateDepartment(departmentId.value, departmentForm)
  else await createDepartment(departmentForm)
  ElMessage.success('部门已保存')
  departmentDialog.value = false
  await load()
}

function editOrganization(item?: OrganizationNode, parent?: OrganizationNode) {
  organizationId.value = item?.id
  Object.assign(organizationForm, item ? {
    department_id: item.department_id, parent_id: item.parent_id ?? null, code: item.code, name: item.name,
    level: item.level, manager_id: item.manager_id ?? null, status: item.status,
  } : {
    department_id: activeDepartment.value || 0, parent_id: parent?.id ?? null, code: '', name: '',
    level: parent ? (`L${Math.min(Number(parent.level.slice(1)) + 1, 4)}` as OrganizationNode['level']) : 'L1', manager_id: null, status: 'active',
  })
  organizationDialog.value = true
}

async function saveOrganization() {
  if (!(await formRef.value?.validate())) return
  if (organizationId.value) await updateOrganization(organizationId.value, organizationForm)
  else await createOrganization(organizationForm)
  ElMessage.success('组织节点已保存')
  organizationDialog.value = false
  tree.value = await getOrganizationTree(activeDepartment.value)
}

function clearToNull() {
  return null
}

async function removeDepartment(item: Department) {
  await ElMessageBox.confirm(
    `确认删除部门“${item.name}”吗？删除前必须先处理部门下的组织、用户和项目。`,
    '删除部门',
    { type: 'warning', confirmButtonText: '确认删除' },
  )
  await deleteDepartment(item.id)
  ElMessage.success('部门已删除')
  await load()
}

async function removeOrganization(item: OrganizationNode) {
  await ElMessageBox.confirm(
    `确认删除组织“${item.name}”吗？请先删除其下级组织，已归属用户将变为未分配组织。`,
    '删除组织',
    { type: 'warning', confirmButtonText: '确认删除' },
  )
  await deleteOrganization(item.id)
  ElMessage.success('组织已删除')
  tree.value = await getOrganizationTree(activeDepartment.value)
}

onMounted(load)
</script>

<template>
  <div class="page-shell">
    <header class="page-header"><div><h1 class="page-title">组织管理</h1><p class="page-subtitle">本地测试数据可维护；标记为 HRDB 的部门和组织只能由同步任务更新。</p></div><div v-if="userStore.hasPermission('organization:edit')"><el-button @click="editDepartment()">新增部门</el-button><el-button type="primary" :disabled="!activeDepartment" @click="editOrganization()">新增组织</el-button></div></header>
    <section class="org-layout">
      <aside class="surface departments">
        <h3>部门</h3>
        <div v-for="item in departments" :key="item.id" class="department-item" :class="{ active: activeDepartment===item.id }" @click="switchDepartment(item.id)">
          <span><strong>{{ item.name }}</strong><small>{{ item.code }}{{ item.data_source==='hrdb' ? ' · HRDB' : '' }}</small></span>
          <span v-if="userStore.hasPermission('organization:edit') && item.data_source!=='hrdb'" class="department-actions"><el-button link size="small" @click.stop="editDepartment(item)">编辑</el-button><el-button link size="small" type="danger" @click.stop="removeDepartment(item)">删除</el-button></span>
        </div>
        <el-empty v-if="!departments.length" description="暂无部门" :image-size="70" />
      </aside>
      <main class="surface tree-card" v-loading="loading">
        <div class="tree-head"><div><h3>组织层级</h3><p>展开节点查看下级组织，最多维护到 L4。</p></div></div>
        <el-tree :data="displayTree" node-key="id" default-expand-all :expand-on-click-node="false">
          <template #default="{ data }">
            <div v-if="data.node_type==='user'" class="tree-node user-node"><div><span class="user-dot"></span><strong>{{ data.name }}</strong><span>{{ data.employee_no }}</span><el-tag v-if="data.status==='disabled'" size="small" type="info">已停用</el-tag></div></div>
            <div v-else-if="data.node_type==='user_group'" class="tree-node group-node"><div><strong>{{ data.name }}</strong><span>{{ data.children.length }} 人</span></div></div>
            <div v-else class="tree-node"><div><el-tag size="small" effect="plain">{{ data.level }}</el-tag><strong>{{ data.name }}</strong><span>{{ data.code }}</span><el-tag v-if="data.data_source==='hrdb'" size="small" type="info" effect="plain">HRDB 只读</el-tag><span v-if="data.manager_name">主管：{{ data.manager_name }}</span><span>{{ data.users?.length || 0 }} 人</span></div><div v-if="userStore.hasPermission('organization:edit') && data.data_source!=='hrdb'"><el-button v-if="data.level!=='L4'" link @click.stop="editOrganization(undefined,data)">添加下级</el-button><el-button link @click.stop="editOrganization(data)">编辑</el-button><el-button link type="danger" @click.stop="removeOrganization(data)">删除</el-button></div></div>
          </template>
        </el-tree>
        <el-empty v-if="!tree.length" description="该部门暂无组织节点" />
      </main>
    </section>

    <el-dialog v-model="departmentDialog" :title="departmentId?'编辑部门':'新增部门'" width="500px">
      <el-form ref="formRef" :model="departmentForm" :rules="rules" label-position="top"><el-form-item label="部门编码" prop="code"><el-input v-model="departmentForm.code" :disabled="Boolean(departmentId)" /></el-form-item><el-form-item label="部门名称" prop="name"><el-input v-model="departmentForm.name" /></el-form-item><el-form-item v-if="departmentId" label="L3（部门负责人/追加工时审批人）"><el-select v-model="departmentForm.manager_id" clearable filterable :value-on-clear="clearToNull" style="width:100%"><el-option v-for="item in l3Users.filter(user=>user.department_id===departmentId)" :key="item.id" :label="`${item.name} (${item.employee_no})`" :value="item.id" /></el-select></el-form-item><el-alert v-else title="请先创建部门，再把 L3 用户分配到该部门，最后回到编辑部门设置负责人。" type="info" :closable="false" show-icon /></el-form>
      <template #footer><el-button @click="departmentDialog=false">取消</el-button><el-button type="primary" @click="saveDepartment">保存</el-button></template>
    </el-dialog>
    <el-dialog v-model="organizationDialog" :title="organizationId?'编辑组织':'新增组织'" width="540px">
      <el-form ref="formRef" :model="organizationForm" :rules="rules" label-position="top"><div class="form-grid"><el-form-item label="组织编码" prop="code"><el-input v-model="organizationForm.code" :disabled="Boolean(organizationId)" /></el-form-item><el-form-item label="层级"><el-select v-model="organizationForm.level" style="width:100%"><el-option v-for="level in ['L1','L2','L3','L4']" :key="level" :label="level" :value="level" /></el-select></el-form-item><el-form-item label="组织名称" prop="name"><el-input v-model="organizationForm.name" /></el-form-item><el-form-item label="主管"><el-select v-model="organizationForm.manager_id" clearable filterable :value-on-clear="clearToNull" style="width:100%"><el-option v-for="item in users" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item></div></el-form>
      <template #footer><el-button @click="organizationDialog=false">取消</el-button><el-button type="primary" @click="saveOrganization">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.org-layout { display: grid; grid-template-columns: 260px 1fr; gap: 16px; min-height: 600px; }
.departments { padding: 14px; }
.departments h3,.tree-card h3 { margin: 6px 8px 16px; color:#273448;font-size:14px; }
.department-item { display:flex;width:100%;align-items:center;justify-content:space-between;border:0;border-radius:10px;background:transparent;padding:11px 12px;text-align:left;cursor:pointer; }
.department-item.active { background:#edf3f9; }
.department-actions { display:flex;align-items:center; }
.departments strong,.departments small { display:block; }.departments strong{color:#445064;font-size:13px}.departments small{margin-top:3px;color:#9aa3b1;font-size:10px}
.tree-card { padding:22px; }.tree-head p{margin:-10px 8px 20px;color:#9aa3b1;font-size:12px}
.tree-node { display:flex;flex:1;align-items:center;justify-content:space-between;padding:9px 6px; }.tree-node>div{display:flex;align-items:center;gap:12px}.tree-node strong{color:#384559}.tree-node span{color:#8c96a5;font-size:12px}.user-node{padding-block:6px}.user-node strong{font-weight:500}.user-dot{width:7px;height:7px;border-radius:50%;background:#7ca0c2}.group-node{border-radius:7px;background:#f6f8fa;padding-inline:10px}
.form-grid { display:grid;grid-template-columns:1fr 1fr;gap:0 16px; }
</style>
