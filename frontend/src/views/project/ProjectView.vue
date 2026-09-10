<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createProject, deleteProject, getProjects, updateProject } from '@/api/project'
import { getDepartmentOptions } from '@/api/organization'
import { getUserOptions } from '@/api/user'
import type { DepartmentOption } from '@/types/organization'
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
const query = reactive({ page: 1, page_size: 20, keyword: '', status: '', manager_id: undefined as number | undefined, department_id: undefined as number | undefined })
const dialogVisible = ref(false)
const editingId = ref<number>()
const formRef = ref<FormInstance>()
const emptyForm = (): ProjectPayload => ({ code: '', name: '', project_type: 'General', manager_id: 0, status: 'Draft', planned_start: '', planned_end: '', priority: 'medium', description: '', remark: '' })
const form = reactive<ProjectPayload>(emptyForm())
const rules: FormRules = {
  code: [{ required: true, message: '请输入项目编号' }], name: [{ required: true, message: '请输入项目名称' }],
  manager_id: [{ required: true, message: '请选择项目经理' }], planned_start: [{ required: true, message: '请选择计划开始日期' }], planned_end: [{ required: true, message: '请选择计划结束日期' }],
}
const statuses = ['Draft','Planned','Running','Suspended','Completed','Cancelled']
const statusLabel: Record<string,string> = { Draft:'草稿',Planned:'已计划',Running:'进行中',Suspended:'暂停',Completed:'已完成',Cancelled:'已取消' }
const statusTypeMap: Record<string, 'primary'|'success'|'warning'|'info'> = { Running:'primary',Completed:'success',Suspended:'warning',Cancelled:'info' }
const statusType = (status: string) => statusTypeMap[status] || ''

async function load() {
  loading.value = true
  try {
    const result = await getProjects({ ...query, keyword: query.keyword || undefined, status: query.status || undefined })
    projects.value = result.items; total.value = result.total
  } finally { loading.value = false }
}
async function loadOptions() {
  ;[departments.value, users.value] = await Promise.all([getDepartmentOptions(), getUserOptions()])
}
function openCreate() { editingId.value=undefined; Object.assign(form,emptyForm()); dialogVisible.value=true }
function openEdit(row: Project) { editingId.value=row.id; Object.assign(form,{ code:row.code,name:row.name,project_type:row.project_type,manager_id:row.manager_id,department_id:row.department_id,status:row.status,planned_start:row.planned_start,planned_end:row.planned_end,actual_start:row.actual_start,actual_end:row.actual_end,priority:row.priority,description:row.description||'',remark:row.remark||'' }); dialogVisible.value=true }
async function save() {
  if (!(await formRef.value?.validate())) return
  if (form.planned_end < form.planned_start) return ElMessage.warning('计划结束日期不能早于开始日期')
  if (editingId.value) {
    const { code: _code, ...payload } = form
    await updateProject(editingId.value,payload)
  } else await createProject(form)
  ElMessage.success('项目已保存'); dialogVisible.value=false; await load()
}
async function remove(row: Project) {
  await ElMessageBox.confirm(`确认删除草稿项目“${row.name}”吗？`,'删除项目',{type:'warning'})
  await deleteProject(row.id); ElMessage.success('项目已删除'); await load()
}
onMounted(async()=>{await loadOptions();await load()})
</script>

<template>
  <div class="page-shell">
    <header class="page-header"><div><h1 class="page-title">项目管理</h1><p class="page-subtitle">维护项目周期、项目经理、成员与状态。</p></div><el-button v-if="userStore.hasPermission('project:edit')" type="primary" @click="openCreate">新建项目</el-button></header>
    <section class="surface filter-bar"><el-input v-model="query.keyword" clearable placeholder="项目编号或名称" style="width:220px" @keyup.enter="query.page=1;load()"/><el-select v-model="query.status" clearable placeholder="项目状态" style="width:150px"><el-option v-for="item in statuses" :key="item" :label="statusLabel[item]" :value="item"/></el-select><el-select v-model="query.manager_id" clearable filterable placeholder="项目经理" style="width:160px"><el-option v-for="item in users" :key="item.id" :label="item.name" :value="item.id"/></el-select><el-select v-model="query.department_id" clearable placeholder="所属部门" style="width:160px"><el-option v-for="item in departments" :key="item.id" :label="item.name" :value="item.id"/></el-select><el-button @click="query.page=1;load()">查询</el-button></section>
    <section class="surface table-card"><el-table v-loading="loading" :data="projects" stripe><el-table-column prop="code" label="项目编号" width="130"/><el-table-column label="项目名称" min-width="190"><template #default="{row}"><el-button link type="primary" @click="$router.push(`/projects/${row.id}`)">{{ row.name }}</el-button></template></el-table-column><el-table-column prop="project_type" label="类型" width="110"/><el-table-column prop="manager_name" label="项目经理" width="110"/><el-table-column prop="department_name" label="部门" min-width="120"/><el-table-column label="状态" width="100"><template #default="{row}"><el-tag :type="statusType(row.status)" effect="light">{{ statusLabel[row.status] }}</el-tag></template></el-table-column><el-table-column label="计划周期" width="205"><template #default="{row}">{{ formatDate(row.planned_start) }} 至 {{ formatDate(row.planned_end) }}</template></el-table-column><el-table-column prop="priority" label="优先级" width="90"/><el-table-column v-if="userStore.hasPermission('project:edit')" label="操作" fixed="right" width="135"><template #default="{row}"><el-button link type="primary" @click="openEdit(row)">编辑</el-button><el-button v-if="row.status==='Draft'" link type="danger" @click="remove(row)">删除</el-button></template></el-table-column></el-table><div class="table-footer"><el-pagination v-model:current-page="query.page" v-model:page-size="query.page_size" :total="total" layout="total, sizes, prev, pager, next" @change="load"/></div></section>

    <el-dialog v-model="dialogVisible" :title="editingId?'编辑项目':'新建项目'" width="720px" destroy-on-close><el-form ref="formRef" :model="form" :rules="rules" label-position="top"><div class="form-grid"><el-form-item label="项目编号" prop="code"><el-input v-model="form.code" :disabled="Boolean(editingId)"/></el-form-item><el-form-item label="项目名称" prop="name"><el-input v-model="form.name"/></el-form-item><el-form-item label="项目类型"><el-input v-model="form.project_type"/></el-form-item><el-form-item label="项目经理" prop="manager_id"><el-select v-model="form.manager_id" filterable style="width:100%"><el-option v-for="item in users" :key="item.id" :label="item.name" :value="item.id"/></el-select></el-form-item><el-form-item label="所属部门"><el-select v-model="form.department_id" clearable style="width:100%"><el-option v-for="item in departments" :key="item.id" :label="item.name" :value="item.id"/></el-select></el-form-item><el-form-item label="项目状态"><el-select v-model="form.status" style="width:100%"><el-option v-for="item in statuses" :key="item" :label="statusLabel[item]" :value="item"/></el-select></el-form-item><el-form-item label="计划开始" prop="planned_start"><el-date-picker v-model="form.planned_start" value-format="YYYY-MM-DD" type="date" style="width:100%"/></el-form-item><el-form-item label="计划结束" prop="planned_end"><el-date-picker v-model="form.planned_end" value-format="YYYY-MM-DD" type="date" style="width:100%"/></el-form-item><el-form-item label="实际开始"><el-date-picker v-model="form.actual_start" value-format="YYYY-MM-DD" type="date" clearable style="width:100%"/></el-form-item><el-form-item label="实际结束"><el-date-picker v-model="form.actual_end" value-format="YYYY-MM-DD" type="date" clearable style="width:100%"/></el-form-item><el-form-item label="优先级"><el-select v-model="form.priority" style="width:100%"><el-option label="高" value="high"/><el-option label="中" value="medium"/><el-option label="低" value="low"/></el-select></el-form-item></div><el-form-item label="项目描述"><el-input v-model="form.description" type="textarea" :rows="3"/></el-form-item><el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="2"/></el-form-item></el-form><template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template></el-dialog>
  </div>
</template>

<style scoped>.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 18px}</style>
