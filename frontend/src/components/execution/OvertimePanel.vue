<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { approveOvertime, createOvertime, getOvertimeRequests, rejectOvertime, withdrawOvertime } from '@/api/overtime'
import type { OvertimeRequest, OvertimeStatus } from '@/types/overtime'
import type { Task } from '@/types/task'
import { useUserStore } from '@/stores/user'
import { beijingNow } from '@/utils/time'
import { formatDateTime } from '@/utils/format'

const props = defineProps<{ tasks: Task[]; refreshKey: number }>()
const emit = defineEmits<{ record: [item: OvertimeRequest] }>()
const userStore = useUserStore()
const route = useRoute()
const loading = ref(false), saving = ref(false), actionId = ref<number>(), dialog = ref(false)
const rows = ref<OvertimeRequest[]>([]), total = ref(0), formRef = ref<FormInstance>()
const initialScope = ['mine', 'approvals', 'related'].includes(String(route.query.scope)) ? String(route.query.scope) : 'mine'
const query = reactive({ page: 1, page_size: 20, scope: initialScope, status: '' })
const labels: Record<OvertimeStatus, string> = { pending: '待审批', approved: '已批准', rejected: '已驳回', withdrawn: '已撤回' }
const tagTypes = { pending: 'warning', approved: 'success', rejected: 'danger', withdrawn: 'info' } as const
const summaryIds = computed(() => new Set(props.tasks.map(item => item.parent_id).filter(Boolean)))
const availableTasks = computed(() => props.tasks.filter(item => item.status !== 'completed' && !summaryIds.value.has(item.id) && item.owner_ids.includes(userStore.profile?.id || -1)))
const form = reactive({ task_id: undefined as number | undefined, date: '', start: '18:00', end: '20:00', reason: '' })
const endOptions = computed(() => Array.from({ length: 48 }, (_, index) => {
  const minutes = (index + 1) * 30
  const value = `${String(Math.floor(minutes / 60)).padStart(2,'0')}:${String(minutes % 60).padStart(2,'0')}`
  return { value, label: minutes === 1440 ? '24:00（次日零点）' : value }
}).filter(item => item.value > form.start))
function endTimestamp() { return form.end === '24:00' ? `${dayjs(form.date).add(1,'day').format('YYYY-MM-DD')}T00:00:00+08:00` : `${form.date}T${form.end}:00+08:00` }
const selectedTask = computed(() => availableTasks.value.find(item => item.id === form.task_id))
const hours = computed(() => {
  const minutes = (value: string) => { const [h,m] = value.split(':').map(Number); return h*60+m }
  const difference = minutes(form.end)-minutes(form.start)
  return form.date && difference > 0 ? difference / 60 : 0
})
const rules: FormRules = {
  task_id: [{ required: true, message: '请选择自己参与的末级任务' }],
  date: [{ required: true, message: '请选择加班日期' }],
  reason: [{ required: true, whitespace: true, message: '请填写加班原因' }],
}
function disabledDate(date: Date) {
  const day = dayjs(date).format('YYYY-MM-DD')
  return day < beijingNow().format('YYYY-MM-DD') || Boolean(selectedTask.value && (day < selectedTask.value.planned_start || day > selectedTask.value.planned_end))
}
async function load() {
  loading.value = true
  try { const result = await getOvertimeRequests({ ...query, status: query.status || undefined }); rows.value = result.items; total.value = result.total }
  catch { /* The request interceptor displays the error. */ }
  finally { loading.value = false }
}
function openCreate() {
  Object.assign(form, { task_id: undefined, date: beijingNow().add(1, 'day').format('YYYY-MM-DD'), start: '18:00', end: '20:00', reason: '' })
  dialog.value = true
}
async function submit() {
  if (!(await formRef.value?.validate().catch(() => false)) || !form.task_id) return
  if (!hours.value) return void ElMessage.warning('结束时间必须晚于开始时间')
  saving.value = true
  try {
    await createOvertime({ task_id: form.task_id, start_time: `${form.date}T${form.start}:00+08:00`, end_time: endTimestamp(), reason: form.reason.trim() })
    ElMessage.success('加班申请已提交，等待审批'); dialog.value = false; query.scope = 'mine'; query.status = ''; query.page = 1; await load()
  } catch { /* Already reported by the request interceptor. */ }
  finally { saving.value = false }
}
async function act(item: OvertimeRequest, action: 'approve' | 'reject' | 'withdraw') {
  let note = ''
  try {
    if (action === 'reject') {
      const result = await ElMessageBox.prompt('请填写驳回原因', '驳回加班申请', { inputType: 'textarea', inputPattern: /\S+/, inputErrorMessage: '原因不能为空' })
      note = result.value.trim()
    } else await ElMessageBox.confirm(action === 'approve' ? `确认批准 ${item.user_name} 的 ${item.hours}h 加班吗？批准后尚不计入实际工时。` : '确认撤回申请吗？撤回后不能再用于填报加班执行。', '加班申请', { type: 'warning' })
  } catch { return }
  actionId.value = item.id
  try {
    if (action === 'approve') await approveOvertime(item.id)
    else if (action === 'reject') await rejectOvertime(item.id, note)
    else await withdrawOvertime(item.id)
    ElMessage.success('已处理'); await load()
  } catch { /* Already reported by the request interceptor. */ }
  finally { actionId.value = undefined }
}
watch(() => props.refreshKey, () => { void load() })
onMounted(() => { void load() })
</script>

<template>
  <section class="overtime-panel">
    <el-alert title="加班仅用于非工作时段，不进入预约看板。项目成员由项目经理审批；项目经理申请自己项目的加班由部门主管审批。批准后须在加班结束后填报执行，才计入实际工时。" type="info" :closable="false" show-icon />
    <div class="surface overtime-toolbar">
      <el-radio-group v-model="query.scope" @change="query.page=1;load()"><el-radio-button value="mine">我的申请</el-radio-button><el-radio-button value="approvals">由我审批</el-radio-button><el-radio-button value="related">相关申请</el-radio-button></el-radio-group>
      <el-select v-model="query.status" clearable placeholder="全部状态" style="width:140px" @change="query.page=1;load()"><el-option v-for="(label,value) in labels" :key="value" :label="label" :value="value" /></el-select>
      <el-button @click="load">刷新</el-button><el-button v-if="userStore.hasPermission('execution:edit')" type="primary" @click="openCreate">申请加班</el-button>
    </div>
    <section class="surface table-card">
      <el-table v-loading="loading" :data="rows" stripe table-layout="fixed">
        <el-table-column prop="project_name" label="项目" min-width="140" show-overflow-tooltip />
        <el-table-column prop="task_name" label="任务" min-width="140" show-overflow-tooltip />
        <el-table-column prop="user_name" label="申请人" min-width="100" />
        <el-table-column label="加班时间（北京时间）" min-width="195"><template #default="{row}">{{formatDateTime(row.start_time)}}<br />至 {{formatDateTime(row.end_time)}}</template></el-table-column>
        <el-table-column label="申请工时" min-width="90"><template #default="{row}">{{row.hours}}h</template></el-table-column>
        <el-table-column label="状态" min-width="125"><template #default="{row}"><el-tag :type="tagTypes[row.status as OvertimeStatus]" size="small">{{labels[row.status as OvertimeStatus]}}</el-tag><small v-if="row.execution_id" class="recorded">已填报执行 #{{row.execution_id}}</small></template></el-table-column>
        <el-table-column prop="approver_name" label="审批人" min-width="100" />
        <el-table-column prop="reason" label="申请原因" min-width="150" show-overflow-tooltip />
        <el-table-column prop="review_note" label="审批说明" min-width="140" show-overflow-tooltip />
        <el-table-column label="操作" min-width="175" fixed="right"><template #default="{row}">
          <template v-if="row.can_review"><el-button link type="primary" :disabled="Boolean(actionId)" @click="act(row,'approve')">批准</el-button><el-button link type="danger" :disabled="Boolean(actionId)" @click="act(row,'reject')">驳回</el-button></template>
          <el-button v-if="row.can_record && userStore.hasPermission('execution:edit')" link type="primary" @click="emit('record',row)">填报执行</el-button>
          <el-button v-if="row.can_withdraw" link :disabled="Boolean(actionId)" @click="act(row,'withdraw')">撤回</el-button>
        </template></el-table-column>
      </el-table>
      <div class="table-footer"><el-pagination v-model:current-page="query.page" :page-size="query.page_size" :total="total" layout="total, prev, pager, next" @change="load" /></div>
    </section>
    <el-dialog v-model="dialog" title="申请加班" width="min(600px, 94vw)" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="项目 / 任务" prop="task_id"><el-select v-model="form.task_id" filterable placeholder="选择自己参与的未完成末级任务" style="width:100%"><el-option v-for="task in availableTasks" :key="task.id" :label="`${task.project_name} / ${task.name}`" :value="task.id" /></el-select></el-form-item>
        <p v-if="selectedTask" class="form-hint">任务计划：{{selectedTask.planned_start}} 至 {{selectedTask.planned_end}} · 预计 {{selectedTask.estimated_hours}}h</p>
        <el-form-item label="加班日期" prop="date"><el-date-picker v-model="form.date" value-format="YYYY-MM-DD" :disabled-date="disabledDate" style="width:100%" /></el-form-item>
        <div class="time-fields"><el-form-item label="开始时间" required><el-time-select v-model="form.start" start="00:00" step="00:30" end="23:30" :clearable="false" style="width:100%" /></el-form-item><el-form-item label="结束时间" required><el-select v-model="form.end" style="width:100%"><el-option v-for="item in endOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></div>
        <p class="form-hint">申请 {{hours}}h · 须在开始前申请并完成审批；以系统工作日历判断非工作时段。跨日请按零点拆分为每日申请。</p>
        <el-form-item label="加班原因" prop="reason"><el-input v-model="form.reason" type="textarea" :rows="3" maxlength="2000" show-word-limit /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" :loading="saving" @click="submit">提交申请</el-button></template>
    </el-dialog>
  </section>
</template>

<style scoped>
.overtime-panel{display:flex;flex-direction:column;gap:16px}.overtime-toolbar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;padding:14px 18px}.time-fields{display:grid;grid-template-columns:1fr 1fr;gap:16px}.recorded{display:block;color:#698271;margin-top:5px;font-size:11px}.form-hint{font-size:12px;color:#7b8797;line-height:1.7;margin:0 0 16px}
</style>
