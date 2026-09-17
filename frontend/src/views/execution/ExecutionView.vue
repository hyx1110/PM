<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createExecution, deleteExecution, getExecutions, updateExecution } from '@/api/execution'
import { getAllTasks } from '@/api/task'
import type { Execution, ExecutionPayload } from '@/types/execution'
import type { Task } from '@/types/task'
import { formatDate } from '@/utils/format'
import { useUserStore } from '@/stores/user'
import { beijingNow } from '@/utils/time'

const userStore=useUserStore(),loading=ref(false),records=ref<Execution[]>([]),tasks=ref<Task[]>([]),total=ref(0)
const query=reactive({page:1,page_size:20,project_id:undefined as number|undefined,task_id:undefined as number|undefined,mine:true,start_date:'',end_date:''})
const dialogVisible=ref(false),editingId=ref<number>(),formRef=ref<FormInstance>()
const emptyForm=():ExecutionPayload=>({task_id:0,user_id:userStore.profile?.id,actual_start:beijingNow().format('YYYY-MM-DD'),actual_end:undefined,actual_hours:undefined,status:'running',description:'',exception_reason:''})
const form=reactive<ExecutionPayload>(emptyForm())
const rules:FormRules={task_id:[{required:true,message:'请选择任务'}],actual_start:[{required:true,message:'请选择实际开始日期'}]}
const statuses=[{value:'running',label:'进行中'},{value:'completed',label:'已完成'},{value:'paused',label:'暂停'}]
const statusLabel=Object.fromEntries(statuses.map((item)=>[item.value,item.label])) as Record<string,string>
const disableFutureDate=(value:Date)=>dayjs(value).format('YYYY-MM-DD')>beijingNow().format('YYYY-MM-DD')
async function load(){if(query.start_date&&query.end_date&&query.end_date<query.start_date){ElMessage.warning('筛选结束日期不能早于开始日期');return}loading.value=true;try{const result=await getExecutions({...query,start_date:query.start_date||undefined,end_date:query.end_date||undefined});records.value=result.items;total.value=result.total}finally{loading.value=false}}
async function loadOptions(){tasks.value=await getAllTasks()}
const canEditRecord=(row:Execution)=>row.user_id===userStore.profile?.id
const myTasks=()=>tasks.value.filter(item=>item.owner_ids.includes(userStore.profile?.id||-1)&&(Boolean(editingId.value)||!['completed','cancelled'].includes(item.status)))
const projects=computed(()=>Array.from(new Map(tasks.value.map(item=>[item.project_id,{id:item.project_id,name:item.project_name||`项目 #${item.project_id}`}])).values()))
function setQuickRange(kind:'today'|'week'|'month'){
  const now=beijingNow()
  const monday=now.subtract((now.day()+6)%7,'day')
  query.start_date=(kind==='today'?now:kind==='week'?monday:now.startOf('month')).format('YYYY-MM-DD')
  query.end_date=(kind==='today'?now:kind==='week'?monday.add(6,'day'):now.endOf('month')).format('YYYY-MM-DD')
  query.page=1;load()
}
function openCreate(){editingId.value=undefined;Object.assign(form,emptyForm());dialogVisible.value=true}
function openEdit(row:Execution){editingId.value=row.id;Object.assign(form,{task_id:row.task_id,user_id:row.user_id,actual_start:row.actual_start,actual_end:row.actual_end,actual_hours:Number(row.actual_hours),status:row.status,description:row.description||'',exception_reason:row.exception_reason||''});dialogVisible.value=true}
async function save(){if(!(await formRef.value?.validate()))return;if(form.actual_end&&form.actual_end<form.actual_start)return ElMessage.warning('实际结束日期不能早于开始日期');if(form.status==='completed'&&!form.actual_end)return ElMessage.warning('已完成记录必须填写实际结束日期');const payload={...form};if(editingId.value){const{task_id:_taskId,user_id:_userId,...updatePayload}=payload;await updateExecution(editingId.value,updatePayload)}else await createExecution(payload);ElMessage.success('执行记录已保存，任务及项目状态已同步');dialogVisible.value=false;await load()}
async function remove(row:Execution){await ElMessageBox.confirm(`确认删除“${row.task_name||'该任务'}”的这条执行记录吗？系统会保留审计数据，但不再计入报表。`,'删除执行记录',{type:'warning',confirmButtonText:'确认删除'});await deleteExecution(row.id);ElMessage.success('执行记录已软删除');await load()}
onMounted(async()=>{await loadOptions();await load()})
</script>

<template>
  <div class="page-shell">
    <header class="page-header"><div><h1 class="page-title">任务执行</h1><p class="page-subtitle">实际起止时间按日期填报；完成记录会自动同步任务和项目状态。</p></div><el-button v-if="userStore.hasPermission('execution:edit')" type="primary" @click="openCreate">填写执行记录</el-button></header>
    <section class="surface filter-bar"><el-select v-model="query.project_id" clearable filterable placeholder="项目" style="width:190px" @change="query.task_id=undefined"><el-option v-for="item in projects" :key="item.id" :label="item.name" :value="item.id"/></el-select><el-select v-model="query.task_id" clearable filterable placeholder="任务" style="width:190px"><el-option v-for="item in tasks.filter(t=>!query.project_id||t.project_id===query.project_id)" :key="item.id" :label="item.name" :value="item.id"/></el-select><el-date-picker v-model="query.start_date" type="date" value-format="YYYY-MM-DD" placeholder="开始日期" style="width:140px"/><el-date-picker v-model="query.end_date" type="date" value-format="YYYY-MM-DD" placeholder="结束日期" style="width:140px"/><el-button-group><el-button @click="setQuickRange('today')">今天</el-button><el-button @click="setQuickRange('week')">本周</el-button><el-button @click="setQuickRange('month')">本月</el-button></el-button-group><el-button type="primary" plain @click="query.page=1;load()">查询</el-button></section>
    <section class="surface table-card"><el-table v-loading="loading" :data="records" stripe><el-table-column prop="project_name" label="项目" min-width="150"/><el-table-column prop="task_name" label="任务" min-width="170"/><el-table-column prop="user_name" label="执行人" width="100"/><el-table-column label="计划日期" width="220"><template #default="{row}">{{formatDate(row.planned_start)}} 至 {{formatDate(row.planned_end)}}</template></el-table-column><el-table-column label="实际日期" width="220"><template #default="{row}">{{formatDate(row.actual_start)}} 至 {{formatDate(row.actual_end)}}</template></el-table-column><el-table-column label="工时" width="80"><template #default="{row}">{{row.actual_hours}}h</template></el-table-column><el-table-column label="状态" width="90"><template #default="{row}">{{statusLabel[row.status]||row.status}}</template></el-table-column><el-table-column prop="description" label="执行说明" min-width="160" show-overflow-tooltip/><el-table-column prop="exception_reason" label="异常原因" min-width="140" show-overflow-tooltip/><el-table-column v-if="userStore.hasPermission('execution:edit')" label="操作" fixed="right" width="125"><template #default="{row}"><template v-if="canEditRecord(row)"><el-button link type="primary" @click="openEdit(row)">编辑</el-button><el-button link type="danger" @click="remove(row)">删除</el-button></template></template></el-table-column></el-table><div class="table-footer"><el-pagination v-model:current-page="query.page" v-model:page-size="query.page_size" :total="total" layout="total, sizes, prev, pager, next" @change="load"/></div></section>
    <el-dialog v-model="dialogVisible" :title="editingId?'编辑执行记录':'填写执行记录'" width="650px"><el-form ref="formRef" :model="form" :rules="rules" label-position="top"><div class="form-grid"><el-form-item label="任务" prop="task_id"><el-select v-model="form.task_id" :disabled="Boolean(editingId)" filterable style="width:100%"><el-option v-for="item in myTasks()" :key="item.id" :label="`${item.project_name} / ${item.name}`" :value="item.id"/></el-select></el-form-item><el-form-item label="状态"><el-select v-model="form.status" style="width:100%"><el-option v-for="item in statuses" :key="item.value" :label="item.label" :value="item.value"/></el-select></el-form-item><el-form-item label="实际开始日期" prop="actual_start"><el-date-picker v-model="form.actual_start" type="date" value-format="YYYY-MM-DD" :disabled-date="disableFutureDate" style="width:100%"/></el-form-item><el-form-item label="实际结束日期"><el-date-picker v-model="form.actual_end" type="date" value-format="YYYY-MM-DD" :disabled-date="disableFutureDate" clearable style="width:100%"/></el-form-item><el-form-item label="实际工时"><el-input-number v-model="form.actual_hours" :min="0.5" :precision="1" style="width:100%"/><div class="field-hint">留空时按所选日期范围内的工作日自动计算；填写值不得超过工作日容量。</div></el-form-item></div><el-form-item label="执行说明"><el-input v-model="form.description" type="textarea" :rows="3"/></el-form-item><el-form-item label="异常原因"><el-input v-model="form.exception_reason" type="textarea" :rows="2"/></el-form-item></el-form><template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template></el-dialog>
  </div>
</template>

<style scoped>.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 18px}.field-hint{margin-top:6px;color:#8d98a6;font-size:11px;line-height:1.5}</style>
