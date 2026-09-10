<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { addProjectMember, getProject, getProjectMembers, removeProjectMember } from '@/api/project'
import { getTasks } from '@/api/task'
import { getSchedules } from '@/api/schedule'
import { getUserOptions } from '@/api/user'
import type { Project, ProjectMember } from '@/types/project'
import type { Schedule } from '@/types/schedule'
import type { Task } from '@/types/task'
import type { UserOption } from '@/types/user'
import { formatDate, formatDateTime } from '@/utils/format'
import { useUserStore } from '@/stores/user'

const route=useRoute(),router=useRouter(),userStore=useUserStore()
const projectId=computed(()=>Number(route.params.id))
const loading=ref(false),project=ref<Project>(),members=ref<ProjectMember[]>([]),tasks=ref<Task[]>([]),schedules=ref<Schedule[]>([]),users=ref<UserOption[]>([])
const activeTab=ref('basic'),memberDialog=ref(false)
const memberForm=reactive({user_id:undefined as number|undefined,project_role:'member',allocation_percent:100,joined_at:''})
async function load(){loading.value=true;try{const [p,m,t,s,u]=await Promise.all([getProject(projectId.value),getProjectMembers(projectId.value),getTasks({project_id:projectId.value,page:1,page_size:200}),getSchedules({project_id:projectId.value,page:1,page_size:200}),getUserOptions()]);project.value=p;members.value=m;tasks.value=t.items;schedules.value=s.items;users.value=u}finally{loading.value=false}}
function openMember(){Object.assign(memberForm,{user_id:undefined,project_role:'member',allocation_percent:100,joined_at:new Date().toISOString().slice(0,10)});memberDialog.value=true}
async function saveMember(){if(!memberForm.user_id)return ElMessage.warning('请选择成员');await addProjectMember(projectId.value,{...memberForm,user_id:memberForm.user_id,joined_at:`${memberForm.joined_at} 00:00:00`});ElMessage.success('成员已添加');memberDialog.value=false;await load()}
async function removeMember(row:ProjectMember){await ElMessageBox.confirm(`确认移除成员“${row.user_name}”吗？`,'移除成员',{type:'warning'});await removeProjectMember(projectId.value,row.user_id);ElMessage.success('成员已移除');await load()}
onMounted(load)
</script>

<template>
  <div class="page-shell" v-loading="loading">
    <header class="page-header"><div><el-button link @click="router.push('/projects')">← 返回项目列表</el-button><h1 class="page-title detail-title">{{ project?.name || '项目详情' }}</h1><p class="page-subtitle">{{ project?.code }} · {{ project?.manager_name }} · {{ project?.status }}</p></div></header>
    <section class="surface detail-card"><el-tabs v-model="activeTab">
      <el-tab-pane label="基本信息" name="basic"><el-descriptions v-if="project" :column="3" border><el-descriptions-item label="项目编号">{{project.code}}</el-descriptions-item><el-descriptions-item label="项目类型">{{project.project_type}}</el-descriptions-item><el-descriptions-item label="状态">{{project.status}}</el-descriptions-item><el-descriptions-item label="项目经理">{{project.manager_name}}</el-descriptions-item><el-descriptions-item label="所属部门">{{project.department_name||'—'}}</el-descriptions-item><el-descriptions-item label="优先级">{{project.priority}}</el-descriptions-item><el-descriptions-item label="计划周期">{{formatDate(project.planned_start)}} 至 {{formatDate(project.planned_end)}}</el-descriptions-item><el-descriptions-item label="实际周期">{{formatDate(project.actual_start)}} 至 {{formatDate(project.actual_end)}}</el-descriptions-item><el-descriptions-item label="描述" :span="3">{{project.description||'—'}}</el-descriptions-item></el-descriptions></el-tab-pane>
      <el-tab-pane name="members"><template #label>项目成员 <el-badge :value="members.length" type="info" /></template><div class="tab-tools"><span>仅展示当前有效成员</span><el-button v-if="userStore.hasPermission('project:edit')" type="primary" size="small" @click="openMember">添加成员</el-button></div><el-table :data="members"><el-table-column prop="user_name" label="成员"/><el-table-column prop="project_role" label="项目角色"/><el-table-column prop="allocation_percent" label="投入比例"><template #default="{row}">{{row.allocation_percent}}%</template></el-table-column><el-table-column label="加入时间"><template #default="{row}">{{formatDate(row.joined_at)}}</template></el-table-column><el-table-column v-if="userStore.hasPermission('project:edit')" label="操作" width="90"><template #default="{row}"><el-button link type="danger" @click="removeMember(row)">移除</el-button></template></el-table-column></el-table></el-tab-pane>
      <el-tab-pane :label="`项目任务 (${tasks.length})`" name="tasks"><div class="tab-tools"><span>项目下一级与二级任务</span><el-button size="small" @click="router.push('/tasks')">进入任务管理</el-button></div><el-table :data="tasks"><el-table-column prop="name" label="任务" min-width="180"/><el-table-column prop="task_type" label="类型"/><el-table-column prop="owner_name" label="负责人"/><el-table-column label="计划时间" width="280"><template #default="{row}">{{formatDateTime(row.planned_start)}} 至 {{formatDateTime(row.planned_end)}}</template></el-table-column><el-table-column prop="effective_status" label="状态"/></el-table></el-tab-pane>
      <el-tab-pane :label="`项目排期 (${schedules.length})`" name="schedules"><div class="tab-tools"><span>该项目当前人力预约</span><el-button size="small" @click="router.push('/schedules')">进入共享看板</el-button></div><el-table :data="schedules"><el-table-column prop="user_name" label="人员"/><el-table-column prop="task_name" label="任务" min-width="180"/><el-table-column label="预约时间" width="290"><template #default="{row}">{{formatDateTime(row.start_time)}} 至 {{formatDateTime(row.end_time)}}</template></el-table-column><el-table-column prop="planned_hours" label="工时"/><el-table-column prop="status" label="状态"/></el-table></el-tab-pane>
    </el-tabs></section>
    <el-dialog v-model="memberDialog" title="添加项目成员" width="500px"><el-form :model="memberForm" label-position="top"><el-form-item label="成员"><el-select v-model="memberForm.user_id" filterable style="width:100%"><el-option v-for="item in users.filter(u=>!members.some(m=>m.user_id===u.id))" :key="item.id" :label="`${item.name} (${item.username})`" :value="item.id"/></el-select></el-form-item><el-form-item label="项目角色"><el-input v-model="memberForm.project_role"/></el-form-item><el-form-item label="投入比例"><el-input-number v-model="memberForm.allocation_percent" :min="0" :max="100" style="width:100%"/></el-form-item><el-form-item label="加入日期"><el-date-picker v-model="memberForm.joined_at" value-format="YYYY-MM-DD" style="width:100%"/></el-form-item></el-form><template #footer><el-button @click="memberDialog=false">取消</el-button><el-button type="primary" @click="saveMember">添加</el-button></template></el-dialog>
  </div>
</template>

<style scoped>.detail-title{margin-top:8px}.detail-card{padding:12px 24px 24px}.tab-tools{display:flex;align-items:center;justify-content:space-between;margin:8px 0 16px;color:#8b95a3;font-size:12px}</style>
