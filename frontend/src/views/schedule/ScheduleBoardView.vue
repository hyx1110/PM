<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { AxiosError } from 'axios'
import { createSchedule, deleteSchedule, getSchedules, submitSchedule, confirmSchedule, rejectSchedule, updateSchedule } from '@/api/schedule'
import { getProjects } from '@/api/project'
import { getTasks } from '@/api/task'
import { getUserOptions } from '@/api/user'
import { getDepartmentOptions } from '@/api/organization'
import ScheduleTimelineHeader from '@/components/schedule/ScheduleTimelineHeader.vue'
import UserScheduleRow from '@/components/schedule/UserScheduleRow.vue'
import ScheduleBookingDialog from '@/components/schedule/ScheduleBookingDialog.vue'
import ScheduleConflictDialog from '@/components/schedule/ScheduleConflictDialog.vue'
import type { ApiResponse } from '@/types/common'
import type { DepartmentOption } from '@/types/organization'
import type { Project } from '@/types/project'
import type { Schedule, ScheduleConflict, SchedulePayload } from '@/types/schedule'
import type { Task } from '@/types/task'
import type { UserOption } from '@/types/user'
import { formatDateTime } from '@/utils/format'
import { useUserStore } from '@/stores/user'

const userStore=useUserStore(),loading=ref(false),viewMode=ref<'day'|'week'>('week'),anchorDate=ref(dayjs().format('YYYY-MM-DD'))
const schedules=ref<Schedule[]>([]),projects=ref<Project[]>([]),tasks=ref<Task[]>([]),users=ref<UserOption[]>([]),departments=ref<DepartmentOption[]>([])
const filter=reactive({project_id:undefined as number|undefined,user_id:undefined as number|undefined,department_id:undefined as number|undefined})
const bookingDialog=ref(false),detailDialog=ref(false),conflictDialog=ref(false),selected=ref<Schedule>(),initialSlot=ref<{userId:number;date:string;hour:number}>(),conflicts=ref<ScheduleConflict[]>([])
const cellWidth=56
const hours=computed(()=>viewMode.value==='day'?Array.from({length:24},(_,i)=>i):Array.from({length:12},(_,i)=>i+8))
const days=computed(()=>{const current=dayjs(anchorDate.value);if(viewMode.value==='day')return[current.format('YYYY-MM-DD')];const monday=current.subtract((current.day()+6)%7,'day');return Array.from({length:7},(_,i)=>monday.add(i,'day').format('YYYY-MM-DD'))})
const visibleUsers=computed(()=>users.value.filter(item=>(!filter.user_id||item.id===filter.user_id)&&(!filter.department_id||item.department_id===filter.department_id)))
const dateTitle=computed(()=>viewMode.value==='day'?dayjs(days.value[0]).format('YYYY年MM月DD日'):`${dayjs(days.value[0]).format('MM月DD日')} - ${dayjs(days.value[6]).format('MM月DD日')}`)
async function load(){loading.value=true;try{const result=await getSchedules({page:1,page_size:500,start_date:days.value[0],end_date:days.value.at(-1),project_id:filter.project_id,user_id:filter.user_id,department_id:filter.department_id});schedules.value=result.items}finally{loading.value=false}}
async function loadOptions(){const[p,t,u,d]=await Promise.all([getProjects({page:1,page_size:200}),getTasks({page:1,page_size:200}),getUserOptions(),getDepartmentOptions()]);projects.value=p.items;tasks.value=t.items;users.value=u;departments.value=d}
function move(step:number){anchorDate.value=dayjs(anchorDate.value).add(step,viewMode.value==='day'?'day':'week').format('YYYY-MM-DD');load()}
function openCreate(slot:{userId:number;date:string;hour:number}){if(!userStore.hasPermission('schedule:edit'))return;selected.value=undefined;initialSlot.value=slot;bookingDialog.value=true}
function openDetail(item:Schedule){selected.value=item;detailDialog.value=true}
function openEdit(){detailDialog.value=false;initialSlot.value=undefined;bookingDialog.value=true}
async function save(payload:SchedulePayload){try{if(selected.value)await updateSchedule(selected.value.id,payload);else await createSchedule(payload);ElMessage.success('预约草稿已保存');bookingDialog.value=false;selected.value=undefined;await load()}catch(error){const response=(error as AxiosError<ApiResponse<{conflicts:ScheduleConflict[]}>>).response;if(response?.status===409){conflicts.value=response.data.data.conflicts;conflictDialog.value=true}}}
async function submit(){if(!selected.value)return;await submitSchedule(selected.value.id);ElMessage.success('预约已提交确认');detailDialog.value=false;await load()}
async function confirm(){if(!selected.value)return;await confirmSchedule(selected.value.id);ElMessage.success('预约已确认');detailDialog.value=false;await load()}
async function reject(){if(!selected.value)return;const{value}=await ElMessageBox.prompt('请输入拒绝原因','拒绝预约',{inputType:'textarea',inputValidator:v=>Boolean(v)||'请填写拒绝原因'});await rejectSchedule(selected.value.id,value);ElMessage.success('预约已拒绝');detailDialog.value=false;await load()}
async function remove(){if(!selected.value)return;await ElMessageBox.confirm('确认删除这条预约吗？','删除预约',{type:'warning'});await deleteSchedule(selected.value.id);ElMessage.success('预约已删除');detailDialog.value=false;await load()}
const canDecide=computed(()=>selected.value&&['pending','changed'].includes(selected.value.status)&&(selected.value.user_id===userStore.profile?.id||userStore.hasPermission('schedule:edit')))
onMounted(async()=>{await loadOptions();await load()})
</script>

<template>
  <div class="page-shell">
    <header class="page-header"><div><h1 class="page-title">任务共享看板</h1><p class="page-subtitle">以人员 × 时间轴统一查看项目、Routine、Training 与 Leave 安排。</p></div><el-button v-if="userStore.hasPermission('schedule:edit')" type="primary" @click="openCreate({userId:userStore.profile?.id||0,date:anchorDate,hour:9})">创建预约</el-button></header>
    <section class="surface board-tools"><div class="filters"><el-select v-model="filter.project_id" clearable filterable placeholder="项目" style="width:190px"><el-option v-for="item in projects" :key="item.id" :label="item.name" :value="item.id"/></el-select><el-select v-model="filter.user_id" clearable filterable placeholder="人员" style="width:150px"><el-option v-for="item in users" :key="item.id" :label="item.name" :value="item.id"/></el-select><el-select v-model="filter.department_id" clearable placeholder="部门" style="width:150px"><el-option v-for="item in departments" :key="item.id" :label="item.name" :value="item.id"/></el-select><el-button @click="load">查询</el-button></div><div class="date-nav"><el-button @click="move(-1)">‹</el-button><el-date-picker v-model="anchorDate" value-format="YYYY-MM-DD" :clearable="false" style="width:140px" @change="load"/><el-button @click="move(1)">›</el-button><el-segmented v-model="viewMode" :options="[{label:'日',value:'day'},{label:'周',value:'week'}]" @change="load"/></div></section>
    <section class="surface board-card" v-loading="loading"><div class="board-caption"><strong>{{dateTitle}}</strong><div class="legend"><span class="project">Project</span><span class="routine">Routine</span><span class="training">Training</span><span class="leave">Leave</span></div></div><div class="board-scroll"><div class="sticky-header"><div class="person-head">人员</div><ScheduleTimelineHeader :days="days" :hours="hours" :cell-width="cellWidth"/></div><UserScheduleRow v-for="user in visibleUsers" :key="user.id" :user-id="user.id" :user-name="user.name" :days="days" :hours="hours" :cell-width="cellWidth" :schedules="schedules" @blank="openCreate" @booking="openDetail"/><el-empty v-if="!visibleUsers.length" description="没有可展示的人员"/></div></section>
    <ScheduleBookingDialog v-model="bookingDialog" :initial="selected" :slot="initialSlot" :projects="projects" :tasks="tasks" :users="users" @save="save"/>
    <ScheduleConflictDialog v-model="conflictDialog" :conflicts="conflicts"/>
    <el-dialog v-model="detailDialog" title="预约详情" width="600px"><el-descriptions v-if="selected" :column="2" border><el-descriptions-item label="人员">{{selected.user_name}}</el-descriptions-item><el-descriptions-item label="状态"><el-tag>{{selected.status}}</el-tag></el-descriptions-item><el-descriptions-item label="项目">{{selected.project_name}}</el-descriptions-item><el-descriptions-item label="任务">{{selected.task_name}}</el-descriptions-item><el-descriptions-item label="开始">{{formatDateTime(selected.start_time)}}</el-descriptions-item><el-descriptions-item label="结束">{{formatDateTime(selected.end_time)}}</el-descriptions-item><el-descriptions-item label="预计工时">{{selected.planned_hours}}h</el-descriptions-item><el-descriptions-item label="备注">{{selected.remark||'—'}}</el-descriptions-item><el-descriptions-item v-if="selected.rejection_reason" label="拒绝原因" :span="2">{{selected.rejection_reason}}</el-descriptions-item></el-descriptions><template #footer><el-button v-if="selected&&['draft','rejected','confirmed'].includes(selected.status)&&userStore.hasPermission('schedule:edit')" @click="openEdit">编辑</el-button><el-button v-if="selected&&['draft','cancelled'].includes(selected.status)&&userStore.hasPermission('schedule:edit')" type="danger" plain @click="remove">删除</el-button><el-button v-if="selected&&['draft','rejected'].includes(selected.status)&&userStore.hasPermission('schedule:edit')" type="primary" @click="submit">提交确认</el-button><el-button v-if="canDecide" type="danger" plain @click="reject">拒绝</el-button><el-button v-if="canDecide" type="success" @click="confirm">同意</el-button></template></el-dialog>
  </div>
</template>

<style scoped>
.board-tools{display:flex;align-items:center;justify-content:space-between;padding:14px 16px}.filters,.date-nav{display:flex;align-items:center;gap:10px}.board-card{overflow:hidden}.board-caption{display:flex;align-items:center;justify-content:space-between;padding:15px 18px;border-bottom:1px solid #e9edf1;color:#455267;font-size:13px}.legend{display:flex;gap:8px}.legend span{border-radius:6px;padding:4px 7px;background:#dfeaf4;color:#355878;font-size:9px}.legend .routine{background:#e4ece9;color:#48685c}.legend .training{background:#eee9f3;color:#6d587f}.legend .leave{background:#f3e9e8;color:#885d59}.board-scroll{max-height:calc(100vh - 290px);overflow:auto}.sticky-header{position:sticky;top:0;z-index:10;display:flex;width:max-content;min-width:100%;box-shadow:0 2px 6px rgba(39,52,70,.06)}.person-head{position:sticky;left:0;z-index:12;display:grid;width:170px;flex:0 0 170px;place-items:center;border-right:1px solid #e2e6eb;background:#fafbfc;color:#7b8595;font-size:11px}
</style>
