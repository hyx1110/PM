<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import dayjs from 'dayjs'
import type { Project } from '@/types/project'
import type { Schedule, SchedulePayload } from '@/types/schedule'
import type { Task } from '@/types/task'
import type { UserOption } from '@/types/user'

const props=defineProps<{modelValue:boolean;initial?:Schedule;slot?:{userId:number;date:string;hour:number};projects:Project[];tasks:Task[];users:UserOption[]}>()
const emit=defineEmits<{ 'update:modelValue':[value:boolean]; save:[payload:SchedulePayload] }>()
const formRef=ref<FormInstance>(),form=reactive<SchedulePayload>({user_id:0,project_id:0,task_id:0,start_time:'',end_time:'',remark:''})
const rules:FormRules={user_id:[{required:true,message:'请选择人员'}],project_id:[{required:true,message:'请选择项目'}],task_id:[{required:true,message:'请选择任务'}],start_time:[{required:true,message:'请选择开始时间'}],end_time:[{required:true,message:'请选择结束时间'}]}
const projectTasks=computed(()=>props.tasks.filter(item=>item.project_id===form.project_id))
watch(()=>props.modelValue,(visible)=>{if(!visible)return;if(props.initial)Object.assign(form,{user_id:props.initial.user_id,project_id:props.initial.project_id,task_id:props.initial.task_id,start_time:props.initial.start_time,end_time:props.initial.end_time,planned_hours:props.initial.planned_hours,remark:props.initial.remark||''});else{const start=props.slot?dayjs(props.slot.date).hour(props.slot.hour).minute(0):dayjs().add(1,'hour').startOf('hour');Object.assign(form,{user_id:props.slot?.userId||0,project_id:0,task_id:0,start_time:start.format('YYYY-MM-DD HH:mm:ss'),end_time:start.add(1,'hour').format('YYYY-MM-DD HH:mm:ss'),planned_hours:1,remark:''})}},{immediate:true})
async function submit(){if(!(await formRef.value?.validate()))return;if(dayjs(form.end_time)<=dayjs(form.start_time))return formRef.value?.validateField('end_time');emit('save',{...form,planned_hours:dayjs(form.end_time).diff(dayjs(form.start_time),'minute')/60})}
</script>

<template>
  <el-dialog :model-value="modelValue" :title="initial?'编辑人力预约':'创建人力预约'" width="620px" destroy-on-close @update:model-value="emit('update:modelValue',$event)">
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top"><div class="form-grid"><el-form-item label="项目" prop="project_id"><el-select v-model="form.project_id" filterable style="width:100%" @change="form.task_id=0"><el-option v-for="item in projects" :key="item.id" :label="item.name" :value="item.id"/></el-select></el-form-item><el-form-item label="任务" prop="task_id"><el-select v-model="form.task_id" filterable style="width:100%"><el-option v-for="item in projectTasks" :key="item.id" :label="item.name" :value="item.id"/></el-select></el-form-item><el-form-item label="人员" prop="user_id"><el-select v-model="form.user_id" filterable style="width:100%"><el-option v-for="item in users" :key="item.id" :label="`${item.name} (${item.username})`" :value="item.id"/></el-select></el-form-item><el-form-item label="预计工时"><el-input-number v-model="form.planned_hours" :min="0" :precision="1" disabled style="width:100%"/></el-form-item><el-form-item label="开始时间" prop="start_time"><el-date-picker v-model="form.start_time" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%"/></el-form-item><el-form-item label="结束时间" prop="end_time" :rules="[{validator:(_r:any,v:string,cb:any)=>dayjs(v)>dayjs(form.start_time)?cb():cb(new Error('结束时间必须晚于开始时间')),trigger:'change'}]"><el-date-picker v-model="form.end_time" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%"/></el-form-item></div><el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="3"/></el-form-item></el-form>
    <template #footer><el-button @click="emit('update:modelValue',false)">取消</el-button><el-button type="primary" @click="submit">保存草稿</el-button></template>
  </el-dialog>
</template>

<style scoped>.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 18px}</style>
