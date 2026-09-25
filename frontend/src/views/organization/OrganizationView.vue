<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Connection, OfficeBuilding, User } from '@element-plus/icons-vue'
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
const activeDepartmentInfo = computed(() => departments.value.find((item) => item.id === activeDepartment.value))
const departmentUsers = computed(() => users.value.filter((item) => item.department_id === activeDepartment.value))
const assignedUserCount = computed(() => departmentUsers.value.filter((item) => item.organization_id).length)
const organizationCount = computed(() => {
  const count = (nodes: OrganizationNode[]): number => nodes.reduce(
    (total, node) => total + 1 + count(node.children || []),
    0,
  )
  return count(tree.value)
})
const departmentManagerName = computed(() => {
  const managerId = activeDepartmentInfo.value?.manager_id
  return managerId ? users.value.find((item) => item.id === managerId)?.name || '未匹配用户' : '暂未设置'
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

function editActiveDepartment() {
  if (activeDepartmentInfo.value) editDepartment(activeDepartmentInfo.value)
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

async function removeActiveDepartment() {
  if (activeDepartmentInfo.value) await removeDepartment(activeDepartmentInfo.value)
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
    <section v-if="departments.length" class="surface org-overview">
      <div class="department-identity">
        <span class="department-icon"><el-icon><OfficeBuilding /></el-icon></span>
        <div class="department-summary">
          <small>当前部门</small>
          <div class="department-picker-row">
            <el-select v-model="activeDepartment" filterable placeholder="选择当前部门" @change="switchDepartment">
              <el-option v-for="item in departments" :key="item.id" :label="item.name" :value="item.id"><span>{{item.name}}</span><small>{{item.code}}</small></el-option>
            </el-select>
            <div v-if="userStore.hasPermission('organization:edit') && activeDepartmentInfo?.data_source!=='hrdb'" class="current-department-actions">
              <el-button link type="primary" @click="editActiveDepartment">编辑</el-button>
              <el-button link type="danger" @click="removeActiveDepartment">删除</el-button>
            </div>
          </div>
          <p>{{activeDepartmentInfo?.code}} · 部门主管：{{departmentManagerName}}</p>
        </div>
      </div>
      <div class="org-metrics">
        <article><span><el-icon><Connection /></el-icon>组织节点</span><strong>{{organizationCount}}</strong></article>
        <article><span><el-icon><User /></el-icon>部门人员</span><strong>{{departmentUsers.length}}</strong></article>
        <article><span>已归属组织</span><strong>{{assignedUserCount}}</strong><small>/ {{departmentUsers.length}}</small></article>
      </div>
    </section>
    <section class="surface tree-card" v-loading="loading">
      <div class="tree-head"><div><span class="eyebrow">ORGANIZATION</span><h3>组织与人员</h3><p>组织层级最多维护到 L4，展开节点即可查看下级组织和所属人员。</p></div><el-button v-if="userStore.hasPermission('organization:edit')" plain :disabled="!activeDepartment" @click="editOrganization()">新增根组织</el-button></div>
      <div v-if="displayTree.length" class="tree-shell">
        <el-tree :data="displayTree" node-key="id" default-expand-all :expand-on-click-node="false">
          <template #default="{ data }">
            <div v-if="data.node_type==='user'" class="tree-node user-node"><div><span class="user-avatar">{{data.name.slice(0,1)}}</span><strong>{{ data.name }}</strong><span>{{ data.employee_no }}</span><el-tag v-if="data.status==='disabled'" size="small" type="info">已停用</el-tag></div></div>
            <div v-else-if="data.node_type==='user_group'" class="tree-node group-node"><div><strong>{{ data.name }}</strong><span>{{ data.children.length }} 人</span></div></div>
            <div v-else class="tree-node organization-node"><div><el-tag size="small" effect="plain">{{ data.level }}</el-tag><strong>{{ data.name }}</strong><span>{{ data.code }}</span><el-tag v-if="data.data_source==='hrdb'" size="small" type="info" effect="plain">HRDB 只读</el-tag><span v-if="data.manager_name">主管：{{ data.manager_name }}</span><span>{{ data.users?.length || 0 }} 人</span></div><div v-if="userStore.hasPermission('organization:edit') && data.data_source!=='hrdb'" class="node-actions"><el-button v-if="data.level!=='L4'" link @click.stop="editOrganization(undefined,data)">添加下级</el-button><el-button link @click.stop="editOrganization(data)">编辑</el-button><el-button link type="danger" @click.stop="removeOrganization(data)">删除</el-button></div></div>
          </template>
        </el-tree>
      </div>
      <el-empty v-else description="该部门暂无组织和人员，可先新增根组织" />
    </section>

    <el-dialog v-model="departmentDialog" :title="departmentId?'编辑部门':'新增部门'" width="500px">
      <el-form ref="formRef" :model="departmentForm" :rules="rules" label-position="top"><el-form-item label="部门编码" prop="code"><el-input v-model="departmentForm.code" :disabled="Boolean(departmentId)" /></el-form-item><el-form-item label="部门名称" prop="name"><el-input v-model="departmentForm.name" /></el-form-item><el-form-item v-if="departmentId" label="部门主管（项目/资源审批人）"><el-select v-model="departmentForm.manager_id" clearable filterable :value-on-clear="clearToNull" style="width:100%"><el-option v-for="item in l3Users.filter(user=>user.department_id===departmentId)" :key="item.id" :label="`${item.name} (${item.employee_no})`" :value="item.id" /></el-select></el-form-item><el-alert v-else title="请先创建部门，再把部门主管用户分配到该部门，最后回到编辑部门设置负责人。" type="info" :closable="false" show-icon /></el-form>
      <template #footer><el-button @click="departmentDialog=false">取消</el-button><el-button type="primary" @click="saveDepartment">保存</el-button></template>
    </el-dialog>
    <el-dialog v-model="organizationDialog" :title="organizationId?'编辑组织':'新增组织'" width="540px">
      <el-form ref="formRef" :model="organizationForm" :rules="rules" label-position="top"><div class="form-grid"><el-form-item label="组织编码" prop="code"><el-input v-model="organizationForm.code" :disabled="Boolean(organizationId)" /></el-form-item><el-form-item label="层级"><el-select v-model="organizationForm.level" style="width:100%"><el-option v-for="level in ['L1','L2','L3','L4']" :key="level" :label="level" :value="level" /></el-select></el-form-item><el-form-item label="组织名称" prop="name"><el-input v-model="organizationForm.name" /></el-form-item><el-form-item label="主管"><el-select v-model="organizationForm.manager_id" clearable filterable :value-on-clear="clearToNull" style="width:100%"><el-option v-for="item in users" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item></div></el-form>
      <template #footer><el-button @click="organizationDialog=false">取消</el-button><el-button type="primary" @click="saveOrganization">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.org-overview{display:flex;align-items:center;justify-content:space-between;gap:28px;padding:22px 26px;background:linear-gradient(135deg,#fff 0%,#f7fafe 100%)}
.department-identity{display:flex;min-width:320px;align-items:center;gap:15px}.department-icon{display:grid;width:46px;height:46px;flex:0 0 46px;place-items:center;border-radius:14px;background:#e7f0f8;color:#416d96;font-size:21px}.department-summary{min-width:0}.department-summary>small,.eyebrow{color:#9aa6b4;font-size:9px;font-weight:700;letter-spacing:.13em}.department-picker-row{display:flex;align-items:center;gap:10px;margin-top:4px}.department-picker-row>.el-select{width:230px}.department-picker-row :deep(.el-select__wrapper){border-radius:10px;background:#fff;box-shadow:0 0 0 1px #dfe7ee inset}.department-picker-row :deep(.el-select__selected-item){color:#263348;font-size:15px;font-weight:650}.department-picker-row :deep(.el-select-dropdown__item){display:flex;justify-content:space-between}.department-picker-row :deep(.el-select-dropdown__item small){color:#9aa6b4;font-size:10px}.current-department-actions{display:flex;align-items:center;white-space:nowrap}.department-identity p{margin:5px 0 0;color:#8995a5;font-size:11px}.org-metrics{display:grid;grid-template-columns:repeat(3,minmax(120px,1fr));gap:12px}.org-metrics article{min-width:128px;border-left:1px solid #e8edf2;padding:3px 18px}.org-metrics span{display:flex;align-items:center;gap:6px;color:#8995a5;font-size:10px}.org-metrics strong{display:inline-block;margin-top:5px;color:#2f3c50;font-size:22px;font-weight:650}.org-metrics small{margin-left:4px;color:#9ca6b3;font-size:11px}
.tree-card{min-width:0;min-height:560px;padding:22px 24px}.tree-head{display:flex;align-items:center;justify-content:space-between;gap:16px;border-bottom:1px solid #edf0f3;padding:0 2px 18px}.tree-head h3{margin:4px 0 0;color:#273448;font-size:15px}.tree-head p{margin:6px 0 0;color:#98a2b0;font-size:11px}.tree-shell{margin-top:14px;border:1px solid #edf0f3;border-radius:14px;background:#fbfcfd;padding:8px 10px 14px}.tree-shell :deep(.el-tree){background:transparent}.tree-shell :deep(.el-tree-node__content){height:auto;min-height:44px;border-radius:9px}.tree-shell :deep(.el-tree-node__content:hover){background:#f2f6f9}
.tree-node{display:flex;min-width:0;flex:1;align-items:center;justify-content:space-between;padding:8px 8px}.tree-node>div{display:flex;min-width:0;align-items:center;gap:11px}.tree-node strong{overflow:hidden;color:#384559;text-overflow:ellipsis;white-space:nowrap}.tree-node span{color:#8c96a5;font-size:11px}.organization-node{border-bottom:1px solid rgba(230,235,240,.72)}.user-node{padding-block:5px}.user-node strong{font-weight:500}.user-avatar{display:grid!important;width:25px;height:25px;flex:0 0 25px;place-items:center;border-radius:9px;background:#e8f0f7;color:#4c7195!important;font-size:9px!important;font-weight:700}.group-node{border-radius:8px;background:#f1f4f7;padding-inline:11px}.node-actions{opacity:.42;transition:opacity .18s}.tree-node:hover .node-actions{opacity:1}
.form-grid { display:grid;grid-template-columns:1fr 1fr;gap:0 16px; }
@media (max-width:900px){.org-overview{align-items:flex-start;flex-direction:column}.org-metrics{width:100%}.org-metrics article:first-child{border-left:0}.department-picker-row{align-items:flex-start;flex-direction:column}.department-picker-row>.el-select{width:min(70vw,280px)}}
</style>
