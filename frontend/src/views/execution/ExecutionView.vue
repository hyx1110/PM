<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import dayjs from 'dayjs'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createExecution, deleteExecution, getExecutions, updateExecution } from '@/api/execution'
import { getAllTasks } from '@/api/task'
import { getDepartmentOptions, getOrganizationTree } from '@/api/organization'
import { getUserOptions } from '@/api/user'
import type { Execution, ExecutionPayload } from '@/types/execution'
import type { DepartmentOption, OrganizationNode } from '@/types/organization'
import type { Task } from '@/types/task'
import type { UserOption } from '@/types/user'
import { formatDate } from '@/utils/format'
import { useUserStore } from '@/stores/user'
import { beijingNow } from '@/utils/time'
import PersonnelScopeCascader from '@/components/common/PersonnelScopeCascader.vue'
import OvertimePanel from '@/components/execution/OvertimePanel.vue'
import { getOvertime } from '@/api/overtime'
import type { OvertimeRequest } from '@/types/overtime'

const userStore=useUserStore(),loading=ref(false),records=ref<Execution[]>([]),tasks=ref<Task[]>([]),total=ref(0)
const users=ref<UserOption[]>([]),departments=ref<DepartmentOption[]>([]),organizations=ref<OrganizationNode[]>([]),filterScopes=ref<string[]>([])
const route=useRoute()
const activeTab=ref(route.query.tab==='overtime'?'overtime':'records'),overtimeRefreshKey=ref(0),overtimeMaxHours=ref<number>(),saving=ref(false)
const hasGlobalAccess=computed(()=>Boolean(userStore.profile?.roles.some(role=>['super_admin','department_manager'].includes(role))))
const query=reactive({page:1,page_size:20,project_id:Number(route.query.project_id)||undefined,task_id:Number(route.query.task_id)||undefined,mine:!hasGlobalAccess.value,start_date:'',end_date:''})
const dialogVisible=ref(false),editingId=ref<number>(),formRef=ref<FormInstance>()
const emptyForm=():ExecutionPayload=>({task_id:0,overtime_request_id:undefined,user_id:userStore.profile?.id,actual_start:beijingNow().format('YYYY-MM-DD'),actual_end:undefined,actual_hours:undefined,status:'running',description:''})
const form=reactive<ExecutionPayload>(emptyForm())
const rules:FormRules={task_id:[{required:true,message:'请选择任务'}],actual_start:[{required:true,message:'请选择实际开始日期'}]}
const statuses=[{value:'running',label:'进行中'},{value:'completed',label:'已完成'}]
const statusLabel=Object.fromEntries(statuses.map((item)=>[item.value,item.label])) as Record<string,string>
const disableFutureDate=(value:Date)=>dayjs(value).format('YYYY-MM-DD')>beijingNow().format('YYYY-MM-DD')
async function load(){if(query.start_date&&query.end_date&&query.end_date<query.start_date){ElMessage.warning('筛选结束日期不能早于开始日期');return}loading.value=true;try{const result=await getExecutions({...query,start_date:query.start_date||undefined,end_date:query.end_date||undefined,personnel_scope:filterScopes.value.length?filterScopes.value.join(','):undefined});records.value=result.items;total.value=result.total}finally{loading.value=false}}
async function loadOptions(){[tasks.value,users.value,departments.value,organizations.value]=await Promise.all([getAllTasks(),getUserOptions(),getDepartmentOptions(),getOrganizationTree()])}
const canEditRecord=(row:Execution)=>hasGlobalAccess.value||row.user_id===userStore.profile?.id
const summaryTaskIds=computed(()=>new Set(tasks.value.map(item=>item.parent_id).filter((id):id is number=>Boolean(id))))
const myTasks=()=>tasks.value.filter(item=>!summaryTaskIds.value.has(item.id)&&(hasGlobalAccess.value||item.owner_ids.includes(userStore.profile?.id||-1))&&(Boolean(editingId.value)||item.status!=='completed'))
const selectedTask=computed(()=>tasks.value.find(item=>item.id===form.task_id))
const executorOptions=computed(()=>selectedTask.value?.owner_ids.map((id,index)=>({id,name:selectedTask.value?.owner_names[index]||`用户 #${id}`}))||[])
function changeTask(){form.user_id=hasGlobalAccess.value?executorOptions.value[0]?.id:userStore.profile?.id}
const projects=computed(()=>Array.from(new Map(tasks.value.map(item=>[item.project_id,{id:item.project_id,name:item.project_name||`项目 #${item.project_id}`}])).values()))
function setQuickRange(kind:'today'|'week'|'month'){
  const now=beijingNow()
  const monday=now.subtract((now.day()+6)%7,'day')
  query.start_date=(kind==='today'?now:kind==='week'?monday:now.startOf('month')).format('YYYY-MM-DD')
  query.end_date=(kind==='today'?now:kind==='week'?monday.add(6,'day'):now.endOf('month')).format('YYYY-MM-DD')
  query.page=1;load()
}
function openCreate(){editingId.value=undefined;overtimeMaxHours.value=undefined;Object.assign(form,emptyForm());if(query.task_id&&myTasks().some(item=>item.id===query.task_id)){form.task_id=query.task_id;changeTask()}dialogVisible.value=true}
function openOvertimeExecution(item:OvertimeRequest){editingId.value=undefined;overtimeMaxHours.value=Number(item.hours);Object.assign(form,emptyForm(),{task_id:item.task_id,user_id:item.user_id,overtime_request_id:item.id,actual_start:item.start_time.slice(0,10),actual_end:dayjs(item.end_time).subtract(1,'minute').format('YYYY-MM-DD'),actual_hours:Number(item.hours),description:`加班：${item.reason}`});dialogVisible.value=true}
async function openEdit(row:Execution){
  try {
    overtimeMaxHours.value=row.overtime_request_id?Number((await getOvertime(row.overtime_request_id)).hours):undefined
    editingId.value=row.id;Object.assign(form,emptyForm(),{task_id:row.task_id,user_id:row.user_id,overtime_request_id:row.overtime_request_id,actual_start:row.actual_start,actual_end:row.actual_end,actual_hours:Number(row.actual_hours),status:row.status,description:row.description||''});dialogVisible.value=true
  } catch { /* The request interceptor displays the error. */ }
}
async function save(){
  if(saving.value||!(await formRef.value?.validate().catch(()=>false)))return
  if(!form.user_id)return ElMessage.warning('请选择执行人')
  if(form.actual_end&&form.actual_end<form.actual_start)return ElMessage.warning('实际结束日期不能早于开始日期')
  if(form.status==='completed'&&!form.actual_end)return ElMessage.warning('已完成记录必须填写实际结束日期')
  saving.value=true
  try {
    const payload={...form}
    if(editingId.value){const{task_id:_taskId,user_id:_userId,overtime_request_id:_overtimeId,...updatePayload}=payload;await updateExecution(editingId.value,updatePayload)}else await createExecution(payload)
    ElMessage.success('执行记录已保存，任务状态与实际工时已更新；项目由负责人确认完成');dialogVisible.value=false;overtimeRefreshKey.value++
    await loadOptions();await load()
  } catch { /* The request interceptor displays the error. */ }
  finally {saving.value=false}
}
async function remove(row:Execution){await ElMessageBox.confirm(`确认删除“${row.task_name||'该任务'}”的这条执行记录吗？系统会保留审计数据，但不再计入报表。`,'删除执行记录',{type:'warning',confirmButtonText:'确认删除'});await deleteExecution(row.id);ElMessage.success('执行记录已软删除');await load()}
onMounted(async()=>{try{await loadOptions();await load()}catch{/* The request interceptor displays the error. */}})
</script>

<template>
  <div class="page-shell">
    <header class="page-header"><div><h1 class="page-title">任务执行</h1><p class="page-subtitle">正常工作先确认预约；非工作时段先申请加班并通过审批，再填报实际执行。</p></div><el-button v-if="activeTab==='records' && userStore.hasPermission('execution:edit')" type="primary" @click="openCreate">填写执行记录</el-button></header>
    <el-radio-group v-model="activeTab"><el-radio-button value="records">执行记录</el-radio-button><el-radio-button value="overtime">加班申请</el-radio-button></el-radio-group>
    <OvertimePanel v-if="activeTab==='overtime'" :tasks="tasks" :refresh-key="overtimeRefreshKey" @record="openOvertimeExecution" />
    <template v-else>
    <section class="surface filter-bar"><el-select v-model="query.project_id" clearable filterable placeholder="项目" style="width:190px" @change="query.task_id=undefined"><el-option v-for="item in projects" :key="item.id" :label="item.name" :value="item.id"/></el-select><el-select v-model="query.task_id" clearable filterable placeholder="任务" style="width:190px"><el-option v-for="item in tasks.filter(t=>!query.project_id||t.project_id===query.project_id)" :key="item.id" :label="item.name" :value="item.id"/></el-select><el-date-picker v-model="query.start_date" type="date" value-format="YYYY-MM-DD" placeholder="开始日期" style="width:140px"/><el-date-picker v-model="query.end_date" type="date" value-format="YYYY-MM-DD" placeholder="结束日期" style="width:140px"/><el-button-group><el-button @click="setQuickRange('today')">今天</el-button><el-button @click="setQuickRange('week')">本周</el-button><el-button @click="setQuickRange('month')">本月</el-button></el-button-group><el-button type="primary" plain @click="query.page=1;load()">查询</el-button></section>
    <section class="surface filter-bar">
      <el-switch v-if="hasGlobalAccess" v-model="query.mine" active-text="只看本人" @change="query.page=1;load()"/>
      <PersonnelScopeCascader v-model="filterScopes" :users="users" :departments="departments" :organizations="organizations" placeholder="部门 / 组织 / 执行人（可多选）" />
      <el-button @click="query.page=1;load()">筛选执行人</el-button>
    </section>
    <section class="surface table-card"><el-table v-loading="loading" :data="records" stripe table-layout="fixed"><el-table-column prop="project_name" label="项目" min-width="135" show-overflow-tooltip/><el-table-column prop="task_name" label="任务" min-width="150" show-overflow-tooltip/><el-table-column prop="user_name" label="执行人" min-width="105" align="center" show-overflow-tooltip/><el-table-column label="计划日期" min-width="170" align="center"><template #default="{row}"><span class="period-cell">{{formatDate(row.planned_start)}}<i>至</i>{{formatDate(row.planned_end)}}</span></template></el-table-column><el-table-column label="实际日期" min-width="170" align="center"><template #default="{row}"><span class="period-cell">{{formatDate(row.actual_start)}}<i>至</i>{{formatDate(row.actual_end)}}</span></template></el-table-column><el-table-column label="预计 / 实际工时" min-width="140" align="center"><template #default="{row}"><div class="hours-comparison" :class="{over:Number(row.task_actual_hours)>Number(row.estimated_hours)}"><strong>{{row.estimated_hours}}h</strong><span>/</span><strong>{{row.task_actual_hours}}h</strong></div></template></el-table-column><el-table-column label="状态" min-width="95" align="center"><template #default="{row}">{{statusLabel[row.status]||row.status}}<el-tag v-if="row.overtime_request_id" type="warning" size="small" style="margin-left:5px">加班</el-tag></template></el-table-column><el-table-column prop="description" label="执行说明" min-width="155" show-overflow-tooltip/><el-table-column v-if="userStore.hasPermission('execution:edit')" label="操作" fixed="right" min-width="120" align="center"><template #default="{row}"><template v-if="canEditRecord(row)"><el-button link type="primary" @click="openEdit(row)">编辑</el-button><el-button link type="danger" @click="remove(row)">删除</el-button></template></template></el-table-column></el-table><div class="table-footer"><el-pagination v-model:current-page="query.page" v-model:page-size="query.page_size" :total="total" layout="total, sizes, prev, pager, next" @change="load"/></div></section>
    </template>
    <el-dialog v-model="dialogVisible" :title="form.overtime_request_id?'填报加班执行':editingId?'编辑执行记录':'填写执行记录'" width="650px">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-alert :title="form.overtime_request_id?`关联加班申请 #${form.overtime_request_id}，已批准 ${overtimeMaxHours}h。仅填写实际完成的加班工时，不要重复包含正常工作工时。`:'实际日期范围内必须存在该执行人已确认的同任务预约；待确认预约不能用于填报执行。'" type="info" :closable="false" show-icon/>
        <div v-if="selectedTask" class="task-hours-summary"><span>任务预计工时</span><strong>{{selectedTask.estimated_hours}}h</strong><small>本次实际工时保存后将累计计入任务实际工时。</small></div>
        <div class="form-grid">
          <el-form-item label="任务" prop="task_id"><el-select v-model="form.task_id" :disabled="Boolean(editingId||form.overtime_request_id)" filterable style="width:100%" @change="changeTask"><el-option v-for="item in myTasks()" :key="item.id" :label="`${item.project_name} / ${item.name}`" :value="item.id"/></el-select></el-form-item>
          <el-form-item v-if="hasGlobalAccess && !editingId && !form.overtime_request_id" label="执行人" required><el-select v-model="form.user_id" filterable style="width:100%" placeholder="请选择任务项目成员"><el-option v-for="item in executorOptions" :key="item.id" :label="item.name" :value="item.id"/></el-select></el-form-item>
          <el-form-item label="状态"><el-select v-model="form.status" style="width:100%"><el-option v-for="item in statuses" :key="item.value" :label="item.label" :value="item.value"/></el-select></el-form-item>
          <el-form-item label="实际开始日期" prop="actual_start"><el-date-picker v-model="form.actual_start" type="date" value-format="YYYY-MM-DD" :disabled="Boolean(form.overtime_request_id)" :disabled-date="disableFutureDate" style="width:100%"/></el-form-item>
          <el-form-item label="实际结束日期"><el-date-picker v-model="form.actual_end" type="date" value-format="YYYY-MM-DD" :disabled="Boolean(form.overtime_request_id)" :disabled-date="disableFutureDate" clearable style="width:100%"/></el-form-item>
          <el-form-item label="实际工时"><el-input-number v-model="form.actual_hours" :min="0.5" :max="form.overtime_request_id?overtimeMaxHours:undefined" :step="0.5" :step-strictly="Boolean(form.overtime_request_id)" :precision="1" style="width:100%"/><div class="field-hint">{{form.overtime_request_id?'加班以 0.5h 计，最多为批准工时；一条申请只关联一条有效执行记录。':'每条记录填写本次新增工时，历史工时累计统计；留空时按所选日期范围内的工作日自动计算。'}}</div></el-form-item>
        </div>
        <el-form-item label="执行说明"><el-input v-model="form.description" type="textarea" :rows="3"/></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 18px}.field-hint{margin-top:6px;color:#8d98a6;font-size:11px;line-height:1.5}
  .hours-comparison{display:inline-flex;align-items:center;gap:6px;border-radius:9px;background:#edf5f1;padding:5px 9px;color:#397157}.hours-comparison span{color:#9aa6a0;font-weight:400}.hours-comparison.over{background:#fff0ef;color:#a94f4a}.task-hours-summary{display:grid;grid-template-columns:1fr auto;align-items:center;margin:14px 0 18px;border:1px solid #e6ebf0;border-radius:12px;background:#f8fafc;padding:12px 14px}.task-hours-summary span{color:#64748b;font-size:12px}.task-hours-summary strong{color:#315f8e;font-size:18px}.task-hours-summary small{grid-column:1/-1;margin-top:4px;color:#98a2b1;font-size:10px}.period-cell{display:inline-grid;grid-template-columns:auto auto auto;gap:5px;align-items:center;white-space:nowrap}.period-cell i{color:#a0a9b6;font-size:11px;font-style:normal}
</style>
