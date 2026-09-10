<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { createTask, getTasks, updateTask } from '@/api/task'
import { getProjects } from '@/api/project'
import { getUserOptions } from '@/api/user'
import type { Project } from '@/types/project'
import type { Task, TaskPayload } from '@/types/task'
import type { UserOption } from '@/types/user'
import { formatDateTime, toApiDateTime } from '@/utils/format'
import { useUserStore } from '@/stores/user'

const userStore=useUserStore(),loading=ref(false),tasks=ref<Task[]>([]),total=ref(0),projects=ref<Project[]>([]),users=ref<UserOption[]>([])
const query=reactive({page:1,page_size:100,project_id:undefined as number|undefined,owner_id:undefined as number|undefined,status:''})
const dialogVisible=ref(false),editingId=ref<number>(),formRef=ref<FormInstance>()
const emptyForm=():TaskPayload=>({project_id:0,parent_id:undefined,name:'',task_type:'Project',owner_id:0,planned_start:'',planned_end:'',estimated_hours:0,status:'not_started',priority:'medium',description:'',remark:''})
const form=reactive<TaskPayload>(emptyForm())
const rules:FormRules={project_id:[{required:true,message:'请选择项目'}],name:[{required:true,message:'请输入任务名称'}],owner_id:[{required:true,message:'请选择负责人'}],planned_start:[{required:true,message:'请选择计划开始时间'}],planned_end:[{required:true,message:'请选择计划结束时间'}]}
const statuses=['not_started','pending','confirmed','running','completed','delayed','cancelled']
const statusLabel:Record<string,string>={not_started:'未开始',pending:'待确认',confirmed:'已确认',running:'进行中',completed:'已完成',delayed:'已延期',cancelled:'已取消'}
const taskTypes=['Project','Routine','Training','Leave','Other']
const parentOptions=computed(()=>tasks.value.filter(item=>item.project_id===form.project_id&&!item.parent_id&&item.id!==editingId.value))
const treeTasks=computed(()=>{
  const roots=tasks.value.filter(item=>!item.parent_id).map(item=>({...item,children:[] as Task[]}))
  const rootMap=new Map(roots.map(item=>[item.id,item]))
  tasks.value.filter(item=>item.parent_id).forEach(item=>rootMap.get(item.parent_id!)?.children?.push({...item}))
  return roots
})
async function load(){loading.value=true;try{const result=await getTasks({...query,status:query.status||undefined});tasks.value=result.items;total.value=result.total}finally{loading.value=false}}
async function loadOptions(){;[projects.value,users.value]=await Promise.all([getProjects({page:1,page_size:200}).then(r=>r.items),getUserOptions()])}
function openCreate(parent?:Task){editingId.value=undefined;Object.assign(form,emptyForm(),parent?{project_id:parent.project_id,parent_id:parent.id}:query.project_id?{project_id:query.project_id}:{});dialogVisible.value=true}
function openEdit(row:Task){editingId.value=row.id;Object.assign(form,{project_id:row.project_id,parent_id:row.parent_id,name:row.name,task_type:row.task_type,owner_id:row.owner_id,planned_start:row.planned_start,planned_end:row.planned_end,estimated_hours:Number(row.estimated_hours),status:row.status,priority:row.priority,description:row.description||'',remark:row.remark||''});dialogVisible.value=true}
async function save(){if(!(await formRef.value?.validate()))return;if(form.planned_end<form.planned_start)return ElMessage.warning('计划结束时间不能早于开始时间');const payload={...form,planned_start:toApiDateTime(form.planned_start)!,planned_end:toApiDateTime(form.planned_end)!};if(editingId.value){const{project_id:_projectId,...updatePayload}=payload;await updateTask(editingId.value,updatePayload)}else await createTask(payload);ElMessage.success('任务已保存');dialogVisible.value=false;await load()}
onMounted(async()=>{await loadOptions();await load()})
</script>

<template>
  <div class="page-shell">
    <header class="page-header"><div><h1 class="page-title">任务管理</h1><p class="page-subtitle">按项目维护一级工作包与二级执行任务。</p></div><el-button v-if="userStore.hasPermission('task:edit')" type="primary" @click="openCreate()">新增任务</el-button></header>
    <section class="surface filter-bar"><el-select v-model="query.project_id" clearable filterable placeholder="项目" style="width:210px"><el-option v-for="item in projects" :key="item.id" :label="`${item.code} · ${item.name}`" :value="item.id"/></el-select><el-select v-model="query.owner_id" clearable filterable placeholder="负责人" style="width:160px"><el-option v-for="item in users" :key="item.id" :label="item.name" :value="item.id"/></el-select><el-select v-model="query.status" clearable placeholder="任务状态" style="width:150px"><el-option v-for="item in statuses" :key="item" :label="statusLabel[item]" :value="item"/></el-select><el-button @click="query.page=1;load()">查询</el-button></section>
    <section class="surface table-card"><el-table v-loading="loading" :data="treeTasks" row-key="id" default-expand-all><el-table-column prop="name" label="任务名称" min-width="220"><template #default="{row}"><span class="task-name" :class="{child:row.parent_id}">{{row.name}}</span></template></el-table-column><el-table-column prop="project_name" label="项目" min-width="160" show-overflow-tooltip/><el-table-column prop="task_type" label="类型" width="100"/><el-table-column prop="owner_name" label="负责人" width="100"/><el-table-column label="计划时间" width="285"><template #default="{row}">{{formatDateTime(row.planned_start)}} 至 {{formatDateTime(row.planned_end)}}</template></el-table-column><el-table-column label="预计工时" width="95"><template #default="{row}">{{row.estimated_hours}}h</template></el-table-column><el-table-column label="状态" width="95"><template #default="{row}"><el-tag :type="row.effective_status==='delayed'?'danger':row.effective_status==='completed'?'success':''" effect="plain">{{statusLabel[row.effective_status]}}</el-tag></template></el-table-column><el-table-column v-if="userStore.hasPermission('task:edit')" label="操作" fixed="right" width="150"><template #default="{row}"><el-button v-if="!row.parent_id" link @click="openCreate(row)">添加子任务</el-button><el-button link type="primary" @click="openEdit(row)">编辑</el-button></template></el-table-column></el-table><div class="table-footer"><el-pagination v-model:current-page="query.page" v-model:page-size="query.page_size" :total="total" :page-sizes="[50,100,200]" layout="total, sizes, prev, pager, next" @change="load"/></div></section>
    <el-dialog v-model="dialogVisible" :title="editingId?'编辑任务':'新增任务'" width="720px" destroy-on-close><el-form ref="formRef" :model="form" :rules="rules" label-position="top"><div class="form-grid"><el-form-item label="所属项目" prop="project_id"><el-select v-model="form.project_id" :disabled="Boolean(editingId)" filterable style="width:100%"><el-option v-for="item in projects" :key="item.id" :label="item.name" :value="item.id"/></el-select></el-form-item><el-form-item label="父任务"><el-select v-model="form.parent_id" clearable :disabled="Boolean(editingId&&form.parent_id)" style="width:100%"><el-option v-for="item in parentOptions" :key="item.id" :label="item.name" :value="item.id"/></el-select></el-form-item><el-form-item label="任务名称" prop="name"><el-input v-model="form.name"/></el-form-item><el-form-item label="任务类型"><el-select v-model="form.task_type" style="width:100%"><el-option v-for="item in taskTypes" :key="item" :value="item"/></el-select></el-form-item><el-form-item label="负责人" prop="owner_id"><el-select v-model="form.owner_id" filterable style="width:100%"><el-option v-for="item in users" :key="item.id" :label="`${item.name} (${item.username})`" :value="item.id"/></el-select></el-form-item><el-form-item label="任务状态"><el-select v-model="form.status" style="width:100%"><el-option v-for="item in statuses" :key="item" :label="statusLabel[item]" :value="item"/></el-select></el-form-item><el-form-item label="计划开始" prop="planned_start"><el-date-picker v-model="form.planned_start" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%"/></el-form-item><el-form-item label="计划结束" prop="planned_end"><el-date-picker v-model="form.planned_end" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%"/></el-form-item><el-form-item label="预计工时"><el-input-number v-model="form.estimated_hours" :min="0" :precision="1" style="width:100%"/></el-form-item><el-form-item label="优先级"><el-select v-model="form.priority" style="width:100%"><el-option label="高" value="high"/><el-option label="中" value="medium"/><el-option label="低" value="low"/></el-select></el-form-item></div><el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="3"/></el-form-item><el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="2"/></el-form-item><div class="form-hint">负责人须为项目经理或当前有效项目成员。</div></el-form><template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template></el-dialog>
  </div>
</template>

<style scoped>.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 18px}.task-name{font-weight:600;color:#39465a}.task-name.child{font-weight:400;color:#5f6b7c}.form-hint{margin-top:-4px;color:#9aa3b1;font-size:11px}</style>
