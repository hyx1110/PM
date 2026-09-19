<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import { getWorkCalendar } from '@/api/work-calendar'
import { getProjectMembers } from '@/api/project'
import type { Project } from '@/types/project'
import type { Schedule, SchedulePayload } from '@/types/schedule'
import type { Task } from '@/types/task'
import type { UserOption } from '@/types/user'
import type { WorkCalendarDay } from '@/types/work-calendar'
import { useUserStore } from '@/stores/user'
import { beijingNow } from '@/utils/time'

const props = defineProps<{
  modelValue: boolean
  initial?: Schedule
  slot?: { userId: number; date: string; time: string }
  projects: Project[]
  tasks: Task[]
  users: UserOption[]
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  save: [payload: SchedulePayload]
}>()
const userStore = useUserStore()
const formRef = ref<FormInstance>()
const form = reactive({
  user_id: 0,
  project_id: 0,
  task_id: 0,
  work_date: '',
  session: 'morning' as 'morning' | 'afternoon',
  start_clock: '08:30',
  end_clock: '09:30',
  remark: '',
})
const calendar = ref<WorkCalendarDay[]>([])
const projectUsers = ref<UserOption[]>([])
const currentProjectMemberIds = ref(new Set<number>())
const loadedYears = new Set<number>()
const rules: FormRules = {
  user_id: [{ required: true, message: '请选择人员' }],
  project_id: [{ required: true, message: '请选择项目' }],
  task_id: [{ required: true, message: '请选择任务' }],
  work_date: [{ required: true, message: '请选择工作日期' }],
}
const projectTasks = computed(() =>
  props.tasks.filter((item) => item.project_id === form.project_id),
)
const startOptions = computed(() =>
  form.session === 'morning'
    ? ['08:30', '09:00', '09:30', '10:00', '10:30', '11:00', '11:30']
    : ['13:00', '13:30', '14:00', '14:30', '15:00', '15:30', '16:00', '16:30', '17:00'],
)
const sessionEnd = computed(() => (form.session === 'morning' ? '12:00' : '17:30'))
const endOptions = computed(() => {
  const values: string[] = []
  let cursor = dayjs(`2000-01-01 ${form.start_clock}`).add(30, 'minute')
  const limit = dayjs(`2000-01-01 ${sessionEnd.value}`)
  while (cursor.isBefore(limit) || cursor.isSame(limit)) {
    values.push(cursor.format('HH:mm'))
    cursor = cursor.add(30, 'minute')
  }
  return values
})
const plannedHours = computed(() => {
  if (!form.work_date || !form.start_clock || !form.end_clock) return 0
  return dayjs(`${form.work_date} ${form.end_clock}`).diff(
    dayjs(`${form.work_date} ${form.start_clock}`),
    'minute',
  ) / 60
})
const projectRemaining = computed(() => {
  const project = props.projects.find((item) => item.id === form.project_id)
  if (!project) return undefined
  return project.remaining_hours
    + (props.initial?.project_id === project.id ? Number(props.initial.planned_hours) : 0)
})
const isSelfBooking = computed(() => {
  const project = props.projects.find((item) => item.id === form.project_id)
  return form.user_id === userStore.profile?.id && project?.manager_id === userStore.profile?.id
})
const availableHours = (project: Project) =>
  project.remaining_hours
  + (props.initial?.project_id === project.id ? Number(props.initial.planned_hours) : 0)

function canBookUserForProject(item: UserOption, project?: Project) {
  if (!project) return false
  const roles = userStore.profile?.roles || []
  const currentUserId = userStore.profile?.id
  return roles.some((role) => ['super_admin', 'department_manager'].includes(role))
    || project.manager_id === currentUserId
}

async function loadProjectUsers(projectId: number) {
  if (!projectId) {
    projectUsers.value = []
    return
  }
  const members = await getProjectMembers(projectId)
  const ids = new Set(members.map((item) => item.user_id))
  currentProjectMemberIds.value = ids
  const project = props.projects.find((item) => item.id === projectId)
  const eligible = props.users.filter(
    (item) => ids.has(item.id) && canBookUserForProject(item, project),
  )
  const lockedUser = props.slot?.userId ? props.users.find((item) => item.id === props.slot?.userId) : undefined
  projectUsers.value = lockedUser && !eligible.some((item) => item.id === lockedUser.id)
    ? [lockedUser, ...eligible]
    : eligible
  if (!props.slot?.userId && !projectUsers.value.some((item) => item.id === form.user_id)) form.user_id = 0
}

async function changeProject(projectId: number) {
  form.task_id = projectTasks.value[0]?.id || 0
  await loadProjectUsers(projectId)
}

async function ensureCalendar(year: number) {
  if (!year || loadedYears.has(year)) return
  const items = await getWorkCalendar(year)
  calendar.value = [
    ...calendar.value.filter((item) => dayjs(item.work_date).year() !== year),
    ...items,
  ]
  loadedYears.add(year)
}

function disabledDate(value: Date) {
  const date = dayjs(value).format('YYYY-MM-DD')
  const override = calendar.value.find((item) => item.work_date === date)
  if (override) return override.day_type === 'holiday'
  const weekday = dayjs(value).day()
  return weekday === 0 || weekday === 6
}

function isValidWorkday(date: string) {
  const override = calendar.value.find((item) => item.work_date === date)
  if (override) return override.day_type === 'workday'
  const weekday = dayjs(date).day()
  return weekday !== 0 && weekday !== 6
}

watch(
  () => props.modelValue,
  async (visible) => {
    if (!visible) return
    if (props.initial) {
      const start = dayjs(props.initial.start_time)
      const end = dayjs(props.initial.end_time)
      Object.assign(form, {
        user_id: props.initial.user_id,
        project_id: props.initial.project_id,
        task_id: props.initial.task_id,
        work_date: start.format('YYYY-MM-DD'),
        session: start.hour() < 12 ? 'morning' : 'afternoon',
        start_clock: start.format('HH:mm'),
        end_clock: end.format('HH:mm'),
        remark: props.initial.remark || '',
      })
    } else {
      const date = props.slot?.date || beijingNow().format('YYYY-MM-DD')
      const clock = props.slot?.time || '08:30'
      const session = clock < '12:00' ? 'morning' : 'afternoon'
      Object.assign(form, {
        user_id: props.slot?.userId || 0,
        project_id: props.projects[0]?.id || 0,
        task_id: 0,
        work_date: date,
        session,
        start_clock: clock,
        end_clock: dayjs(`2000-01-01 ${clock}`).add(60, 'minute').format('HH:mm'),
        remark: '',
      })
      form.task_id = projectTasks.value[0]?.id || 0
    }
    await loadProjectUsers(form.project_id)
    await ensureCalendar(dayjs(form.work_date).year())
  },
  { immediate: true },
)

watch(
  () => form.work_date,
  (value) => {
    if (value) ensureCalendar(dayjs(value).year())
  },
)

function resetSessionTimes() {
  form.start_clock = form.session === 'morning' ? '08:30' : '13:00'
  form.end_clock = form.session === 'morning' ? '09:30' : '14:00'
}

watch(
  () => form.start_clock,
  () => {
    if (!endOptions.value.includes(form.end_clock)) {
      form.end_clock = endOptions.value[0]
    }
  },
)

async function submit() {
  if (!(await formRef.value?.validate())) return
  if (!currentProjectMemberIds.value.has(form.user_id)) {
    return ElMessage.warning('当前人员不是所选项目的有效成员，请更换项目')
  }
  if (!isValidWorkday(form.work_date)) {
    return ElMessage.warning('只能预约工作日，法定节假日不能预约')
  }
  if (plannedHours.value <= 0) return ElMessage.warning('请选择有效的预约时段')
  if (projectRemaining.value !== undefined && plannedHours.value > projectRemaining.value) {
    return ElMessage.warning('项目剩余工时不足，请先申请追加工时并等待 L3 审批')
  }
  emit('save', {
    user_id: form.user_id,
    project_id: form.project_id,
    task_id: form.task_id,
    start_time: `${form.work_date} ${form.start_clock}:00`,
    end_time: `${form.work_date} ${form.end_clock}:00`,
    planned_hours: plannedHours.value,
    remark: form.remark,
  })
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="initial ? '编辑人力预约' : '提交人力预约'"
    width="640px"
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-alert title="仅可使用有权管理且已审批的项目预约有效成员；项目负责人预约自己时自动确认，其他预约由被预约人确认。" type="info" :closable="false" show-icon/>
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
      <div class="form-grid">
        <el-form-item label="项目" prop="project_id">
          <el-select v-model="form.project_id" filterable style="width:100%" @change="changeProject">
            <el-option v-for="item in projects" :key="item.id" :label="`${item.name}（本次可用 ${availableHours(item)}h）`" :value="item.id"/>
          </el-select>
        </el-form-item>
        <el-form-item label="任务" prop="task_id">
          <el-select v-model="form.task_id" filterable style="width:100%">
            <el-option v-for="item in projectTasks" :key="item.id" :label="item.name" :value="item.id"/>
          </el-select>
        </el-form-item>
        <el-form-item label="人员" prop="user_id">
          <el-select v-model="form.user_id" filterable :disabled="Boolean(slot?.userId)" style="width:100%">
            <el-option v-for="item in projectUsers" :key="item.id" :label="`${item.name} (${item.employee_no})`" :value="item.id"/>
          </el-select>
        </el-form-item>
        <el-form-item label="自动计算工时"><el-input :model-value="`${plannedHours} 小时`" disabled/></el-form-item>
        <el-form-item label="工作日期" prop="work_date">
          <el-date-picker v-model="form.work_date" type="date" value-format="YYYY-MM-DD" :disabled-date="disabledDate" style="width:100%"/>
        </el-form-item>
        <el-form-item label="工作时段">
          <el-radio-group v-model="form.session" @change="resetSessionTimes">
            <el-radio-button value="morning">上午 08:30-12:00</el-radio-button>
            <el-radio-button value="afternoon">下午 13:00-17:30</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="开始时间">
          <el-select v-model="form.start_clock" style="width:100%">
            <el-option v-for="item in startOptions" :key="item" :label="item" :value="item"/>
          </el-select>
        </el-form-item>
        <el-form-item label="结束时间">
          <el-select v-model="form.end_clock" style="width:100%">
            <el-option v-for="item in endOptions" :key="item" :label="item" :value="item"/>
          </el-select>
        </el-form-item>
      </div>
      <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="3"/></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" @click="submit">{{ isSelfBooking ? (initial ? '保存并自动确认' : '预约并自动确认') : (initial ? '保存并重新待确认' : '预约') }}</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 18px}
</style>
