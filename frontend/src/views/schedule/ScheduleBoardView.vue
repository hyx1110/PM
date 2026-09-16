<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { AxiosError } from 'axios'
import {
  batchCreateSchedules,
  confirmSchedule,
  copyScheduleWeek,
  createSchedule,
  deleteSchedule,
  getSchedules,
  moveSchedule,
  rejectSchedule,
  updateSchedule,
  withdrawSchedule,
} from '@/api/schedule'
import { getProjectMembers, getProjects } from '@/api/project'
import { getTasks } from '@/api/task'
import { getScheduleUserOptions } from '@/api/user'
import { getDepartmentOptions, getOrganizationTree } from '@/api/organization'
import { getWorkCalendar } from '@/api/work-calendar'
import {
  createPersonalTimeBlock,
  getMyPersonalTimeBlocks,
  getPersonalTimeBlocks,
  withdrawPersonalTimeBlock,
} from '@/api/personal-time'
import ScheduleTimelineHeader from '@/components/schedule/ScheduleTimelineHeader.vue'
import UserScheduleRow from '@/components/schedule/UserScheduleRow.vue'
import ScheduleBookingDialog from '@/components/schedule/ScheduleBookingDialog.vue'
import ScheduleConflictDialog from '@/components/schedule/ScheduleConflictDialog.vue'
import PersonalTimeDialog from '@/components/schedule/PersonalTimeDialog.vue'
import type { ApiResponse } from '@/types/common'
import type { DepartmentOption, OrganizationNode } from '@/types/organization'
import type { Project } from '@/types/project'
import type { PersonalTimeBlock, PersonalTimePayload } from '@/types/personal-time'
import type { Schedule, ScheduleConflict, SchedulePayload } from '@/types/schedule'
import type { Task } from '@/types/task'
import type { UserOption } from '@/types/user'
import type { ScheduleDayMeta, WorkCalendarDay } from '@/types/work-calendar'
import { formatDateTime } from '@/utils/format'
import { useUserStore } from '@/stores/user'
import { beijingNow } from '@/utils/time'

const userStore = useUserStore()
const loading = ref(false)
const viewMode = ref<'day' | 'week' | 'month'>('week')
const anchorDate = ref(beijingNow().format('YYYY-MM-DD'))
const schedules = ref<Schedule[]>([])
const hiddenBoardStatuses = new Set(['draft', 'rejected', 'withdrawn', 'cancelled'])
const boardSchedules = computed(() =>
  schedules.value.filter((item) => !hiddenBoardStatuses.has(item.status)),
)
const personalBlocks = ref<PersonalTimeBlock[]>([])
const projects = ref<Project[]>([])
const tasks = ref<Task[]>([])
const users = ref<UserOption[]>([])
const departments = ref<DepartmentOption[]>([])
const organizations = ref<OrganizationNode[]>([])
const filter = reactive({
  project_id: undefined as number | undefined,
  user_id: undefined as number | undefined,
  department_id: undefined as number | undefined,
  organization_id: undefined as number | undefined,
  employee_no: '',
  name: '',
})
const bookingDialog = ref(false)
const detailDialog = ref(false)
const personalDialog = ref(false)
const personalDetailDialog = ref(false)
const myTimeDrawer = ref(false)
const personDrawer = ref(false)
const conflictDialog = ref(false)
const batchDialog = ref(false)
const batchSaving = ref(false)
const batchUsers = ref<UserOption[]>([])
const selected = ref<Schedule>()
const selectedPersonalBlock = ref<PersonalTimeBlock>()
const personalInitialSlot = ref<{ date: string; time: string }>()
const myTimeRows = ref<PersonalTimeBlock[]>([])
const myTimeTotal = ref(0)
const myTimeLoading = ref(false)
const myTimeQuery = reactive({
  page: 1,
  page_size: 20,
  status: '' as '' | 'active' | 'withdrawn',
})
const selectedPerson = ref<{ userId: number; userName: string }>()
const personSchedules = ref<Schedule[]>([])
const personTotal = ref(0)
const personLoading = ref(false)
const personQuery = reactive({ page: 1, page_size: 20, status: '' })
const initialSlot = ref<{ userId: number; date: string; time: string }>()
const conflicts = ref<ScheduleConflict[]>([])
const calendarDays = ref<WorkCalendarDay[]>([])
const loadedCalendarYears = new Set<number>()
const batchForm = reactive({
  user_ids: [] as number[],
  project_id: 0,
  task_id: 0,
  work_date: '',
  session: 'morning' as 'morning' | 'afternoon',
  start_clock: '08:30',
  end_clock: '09:30',
  remark: '',
})
const cellWidth = 46
const slots = [
  '08:00', '08:30', '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
  '12:00', '12:30', '13:00', '13:30', '14:00', '14:30', '15:00', '15:30',
  '16:00', '16:30', '17:00', '17:30',
]
const statusLabel: Record<string, string> = {
  draft: '旧版草稿',
  pending: '待本人确认',
  confirmed: '已确认',
  rejected: '已拒绝',
  changed: '变更待确认',
  running: '进行中',
  completed: '已完成',
  cancelled: '已取消',
  withdrawn: '已撤回',
}
const statusTagType: Record<string, 'info' | 'success' | 'warning' | 'danger'> = {
  draft: 'info',
  pending: 'warning',
  confirmed: 'success',
  rejected: 'danger',
  changed: 'warning',
  running: 'success',
  completed: 'info',
  cancelled: 'info',
  withdrawn: 'info',
}
const personalTypeLabel: Record<string, string> = {
  training: '培训',
  meeting: '会议',
  leave: '休假',
  out_of_office: '外出',
  business_trip: '出差',
  other: '其他安排',
}
const weekDays = computed(() => {
  const current = dayjs(anchorDate.value)
  const monday = current.subtract((current.day() + 6) % 7, 'day')
  return Array.from({ length: 7 }, (_, index) =>
    monday.add(index, 'day').format('YYYY-MM-DD'),
  )
})
const days = computed(() =>
  viewMode.value === 'day'
    ? [dayjs(anchorDate.value).format('YYYY-MM-DD')]
    : weekDays.value,
)
const monthDays = computed(() => {
  const first = dayjs(anchorDate.value).startOf('month')
  const start = first.subtract((first.day() + 6) % 7, 'day')
  return Array.from({ length: 42 }, (_, index) =>
    start.add(index, 'day').format('YYYY-MM-DD'),
  )
})
const range = computed(() =>
  viewMode.value === 'month'
    ? { start: monthDays.value[0], end: monthDays.value.at(-1)! }
    : { start: days.value[0], end: days.value.at(-1)! },
)
const timelineDayMeta = computed<Record<string, ScheduleDayMeta>>(() =>
  Object.fromEntries(days.value.map((date) => [date, scheduleDayMeta(date)])),
)
const visibleUsers = computed(() => {
  const filtered = users.value.filter(
    (item) =>
      (!filter.user_id || item.id === filter.user_id)
      && (!filter.department_id || item.department_id === filter.department_id),
  )
  const current = users.value.find((item) => item.id === userStore.profile?.id)
  return current
    ? [current, ...filtered.filter((item) => item.id !== current.id)]
    : filtered
})
const flatOrganizations = computed(() => {
  const result: Array<OrganizationNode & { label: string }> = []
  const walk = (nodes: OrganizationNode[], prefix = '') => nodes.forEach((node) => {
    result.push({ ...node, label: `${prefix}${node.name}` })
    walk(node.children || [], `${prefix}　`)
  })
  walk(organizations.value)
  return result
})
const bookableProjects = computed(() => {
  const roles = userStore.profile?.roles || []
  const currentUserId = userStore.profile?.id
  return projects.value.filter((item) => {
    if (
      item.approval_status !== 'approved'
      || ['Completed', 'Cancelled'].includes(item.status)
    ) return false
    return item.manager_id === currentUserId && roles.includes('project_manager')
  })
})
const canBook = computed(
  () =>
    userStore.hasPermission('schedule:edit')
    && userStore.profile?.roles.includes('project_manager'),
)
const dateTitle = computed(() =>
  viewMode.value === 'day'
    ? dayjs(days.value[0]).format('YYYY年MM月DD日')
    : viewMode.value === 'week'
      ? `${dayjs(days.value[0]).format('MM月DD日')} - ${dayjs(days.value[6]).format('MM月DD日')}`
      : dayjs(anchorDate.value).format('YYYY年MM月'),
)
const batchTasks = computed(() =>
  tasks.value.filter((item) => item.project_id === batchForm.project_id),
)

function canBookUserForProject(item: UserOption, project?: Project) {
  if (!project) return false
  const roles = userStore.profile?.roles || []
  const currentUserId = userStore.profile?.id
  return project.manager_id === currentUserId && roles.includes('project_manager')
}

async function loadBatchUsers(projectId: number) {
  const members = await getProjectMembers(projectId)
  const ids = new Set(members.map((item) => item.user_id))
  const project = bookableProjects.value.find((item) => item.id === projectId)
  batchUsers.value = users.value.filter(
    (item) => ids.has(item.id) && canBookUserForProject(item, project),
  )
  batchForm.user_ids = batchForm.user_ids.filter((id) => ids.has(id))
}
async function changeBatchProject(projectId: number) {
  batchForm.task_id = batchTasks.value[0]?.id || 0
  await loadBatchUsers(projectId)
}
const batchStartOptions = computed(() =>
  batchForm.session === 'morning'
    ? ['08:30', '09:00', '09:30', '10:00', '10:30', '11:00', '11:30']
    : ['13:00', '13:30', '14:00', '14:30', '15:00', '15:30', '16:00', '16:30', '17:00'],
)
const batchEndOptions = computed(() => {
  const values: string[] = []
  const limit = dayjs(
    `2000-01-01 ${batchForm.session === 'morning' ? '12:00' : '17:30'}`,
  )
  let cursor = dayjs(`2000-01-01 ${batchForm.start_clock}`).add(30, 'minute')
  while (cursor.isBefore(limit) || cursor.isSame(limit)) {
    values.push(cursor.format('HH:mm'))
    cursor = cursor.add(30, 'minute')
  }
  return values
})
const batchHours = computed(() =>
  dayjs(`2000-01-01 ${batchForm.end_clock}`).diff(
    dayjs(`2000-01-01 ${batchForm.start_clock}`),
    'minute',
  ) / 60,
)
const canDecide = computed(
  () =>
    selected.value
    && ['pending', 'changed'].includes(selected.value.status)
    && selected.value.user_id === userStore.profile?.id,
)
const canEdit = computed(
  () =>
    selected.value
    && ['pending', 'rejected', 'confirmed'].includes(selected.value.status)
    && selected.value.created_by === userStore.profile?.id
    && bookableProjects.value.some((item) => item.id === selected.value?.project_id),
)
const canWithdraw = computed(
  () =>
    userStore.hasPermission('schedule:edit')
    && selected.value
    && ['pending', 'changed'].includes(selected.value.status)
    && selected.value.created_by === userStore.profile?.id,
)
const canDelete = computed(
  () =>
    selected.value
    && ['draft', 'rejected', 'cancelled', 'withdrawn'].includes(selected.value.status)
    && selected.value.created_by === userStore.profile?.id,
)

function daySchedules(date: string) {
  const visibleUserIds = new Set(visibleUsers.value.map((item) => item.id))
  return boardSchedules.value.filter(
    (item) =>
      dayjs(item.start_time).format('YYYY-MM-DD') === date
      && visibleUserIds.has(item.user_id),
  )
}

function dayPersonalBlocks(date: string) {
  return personalBlocks.value.filter(
    (item) =>
      dayjs(item.start_time).format('YYYY-MM-DD') === date
      && visibleUsers.value.some((user) => user.id === item.user_id),
  )
}

async function loadCalendar(year: number) {
  if (loadedCalendarYears.has(year)) return
  const items = await getWorkCalendar(year)
  calendarDays.value = [
    ...calendarDays.value.filter((item) => Number(item.work_date.slice(0, 4)) !== year),
    ...items,
  ]
  loadedCalendarYears.add(year)
}

function scheduleDayMeta(date: string): ScheduleDayMeta {
  const override = calendarDays.value.find((item) => item.work_date === date)
  if (override?.day_type === 'holiday') return { kind: 'holiday', name: override.name }
  if (override?.day_type === 'workday') return { kind: 'workday', name: override.name }
  if ([0, 6].includes(dayjs(date).day())) return { kind: 'weekend', name: '周末休息' }
  return { kind: 'workday' }
}

async function loadVisibleCalendars() {
  const visibleDates = viewMode.value === 'month' ? monthDays.value : days.value
  const years = [...new Set(visibleDates.map((date) => dayjs(date).year()))]
  await Promise.all(years.map(loadCalendar))
}

function disabledBatchDate(value: Date) {
  const date = dayjs(value).format('YYYY-MM-DD')
  const override = calendarDays.value.find((item) => item.work_date === date)
  if (override) return override.day_type === 'holiday'
  return [0, 6].includes(dayjs(value).day())
}

function batchDateIsWorkday() {
  const override = calendarDays.value.find((item) => item.work_date === batchForm.work_date)
  if (override) return override.day_type === 'workday'
  return ![0, 6].includes(dayjs(batchForm.work_date).day())
}

async function load() {
  loading.value = true
  try {
    await loadVisibleCalendars()
    const [scheduleResult, personalResult] = await Promise.all([
      getSchedules({
        page: 1,
        page_size: 500,
        start_date: range.value.start,
        end_date: range.value.end,
        project_id: filter.project_id,
      }),
      getPersonalTimeBlocks({
        page: 1,
        page_size: 500,
        start_date: range.value.start,
        end_date: range.value.end,
        status: 'active',
      }),
    ])
    schedules.value = scheduleResult.items
    personalBlocks.value = personalResult.items
  } finally {
    loading.value = false
  }
}

async function loadOptions() {
  const [projectResult, taskResult, userResult, departmentResult, organizationResult] = await Promise.all([
    getProjects({ page: 1, page_size: 200 }),
    getTasks({ page: 1, page_size: 200 }),
    getScheduleUserOptions({
      project_id: filter.project_id,
      name: filter.name || undefined,
      employee_no: filter.employee_no || undefined,
      department_id: filter.department_id,
      organization_id: filter.organization_id,
    }),
    getDepartmentOptions(),
    getOrganizationTree(),
  ])
  projects.value = projectResult.items
  tasks.value = taskResult.items
  users.value = userResult
  departments.value = departmentResult
  organizations.value = organizationResult
}

async function applyFilters() {
  await loadOptions()
  await load()
}

function move(step: number) {
  anchorDate.value = dayjs(anchorDate.value)
    .add(step, viewMode.value === 'day' ? 'day' : viewMode.value === 'week' ? 'week' : 'month')
    .format('YYYY-MM-DD')
  load()
}

function openCreate(slot: { userId: number; date: string; time: string }) {
  if (!canBook.value) return
  if (!bookableProjects.value.length) {
    return ElMessage.warning('没有当前权限可预约的已审批项目')
  }
  selected.value = undefined
  initialSlot.value = slot
  bookingDialog.value = true
}

function openBookingButton() {
  openCreate({ userId: 0, date: anchorDate.value, time: '08:30' })
}

function openPersonalCreate(slot?: { date: string; time: string }) {
  personalInitialSlot.value = slot || {
    date: anchorDate.value,
    time: '08:30',
  }
  personalDialog.value = true
}

function handleBlankSlot(slot: { userId: number; date: string; time: string }) {
  if (slot.userId === userStore.profile?.id) {
    openPersonalCreate({ date: slot.date, time: slot.time })
    return
  }
  openCreate(slot)
}

async function savePersonalTime(payload: PersonalTimePayload) {
  try {
    await createPersonalTimeBlock(payload)
    personalDialog.value = false
    ElMessage.success('个人时间安排已保存，该时段已设置为不可预约')
    await load()
    if (myTimeDrawer.value) await loadMyTimeBlocks()
  } catch (error) {
    showConflict(error)
  }
}

function openPersonalBlock(item: PersonalTimeBlock) {
  selectedPersonalBlock.value = item
  personalDetailDialog.value = true
}

async function loadMyTimeBlocks() {
  myTimeLoading.value = true
  try {
    const result = await getMyPersonalTimeBlocks({
      page: myTimeQuery.page,
      page_size: myTimeQuery.page_size,
      status: myTimeQuery.status || undefined,
    })
    myTimeRows.value = result.items
    myTimeTotal.value = result.total
  } finally {
    myTimeLoading.value = false
  }
}

async function openMyTimeDrawer() {
  Object.assign(myTimeQuery, { page: 1, status: '' })
  myTimeDrawer.value = true
  await loadMyTimeBlocks()
}

async function withdrawPersonalBlock(item?: PersonalTimeBlock) {
  const target = item || selectedPersonalBlock.value
  if (!target || target.status !== 'active') return
  await ElMessageBox.confirm(
    `确定撤回 ${personalTypeLabel[target.time_type]}（${formatDateTime(target.start_time)} 至 ${dayjs(target.end_time).format('HH:mm')}）吗？撤回后该时段将重新允许预约。`,
    '撤回个人时间安排',
    { type: 'warning', confirmButtonText: '确认撤回' },
  )
  await withdrawPersonalTimeBlock(target.id)
  ElMessage.success('个人时间安排已撤回，该时段已释放')
  personalDetailDialog.value = false
  await load()
  if (myTimeDrawer.value) await loadMyTimeBlocks()
}

function openMonthCreate(date: string) {
  const meta = scheduleDayMeta(date)
  if (meta.kind !== 'workday') {
    return ElMessage.warning(meta.kind === 'holiday' ? `${meta.name || '法定节假日'}不可预约` : '周末不可预约')
  }
  openPersonalCreate({ date, time: '08:30' })
}

function openDetail(item: Schedule) {
  selected.value = item
  detailDialog.value = true
}

async function loadPersonSchedules() {
  if (!selectedPerson.value) return
  personLoading.value = true
  try {
    const result = await getSchedules({
      page: personQuery.page,
      page_size: personQuery.page_size,
      user_id: selectedPerson.value.userId,
      status: personQuery.status || undefined,
      sort_order: 'desc',
    })
    personSchedules.value = result.items
    personTotal.value = result.total
  } finally {
    personLoading.value = false
  }
}

async function openPersonSchedules(person: { userId: number; userName: string }) {
  selectedPerson.value = person
  Object.assign(personQuery, { page: 1, status: '' })
  personSchedules.value = []
  personTotal.value = 0
  personDrawer.value = true
  await loadPersonSchedules()
}

function openPersonScheduleDetail(item: Schedule) {
  personDrawer.value = false
  openDetail(item)
}

function openEdit() {
  detailDialog.value = false
  initialSlot.value = undefined
  bookingDialog.value = true
}

function showConflict(error: unknown) {
  const response = (error as AxiosError<ApiResponse<{ conflicts?: ScheduleConflict[] }>>).response
  if (response?.status === 409 && response.data.data?.conflicts) {
    conflicts.value = response.data.data.conflicts
    conflictDialog.value = true
    return true
  }
  return false
}

async function save(payload: SchedulePayload) {
  try {
    if (selected.value) {
      await updateSchedule(selected.value.id, payload)
      ElMessage.success('预约已修改，等待被预约人重新确认')
    } else {
      await createSchedule(payload)
      ElMessage.success('预约已提交，等待被预约人本人确认')
    }
    bookingDialog.value = false
    selected.value = undefined
    await loadOptions()
    await load()
  } catch (error) {
    showConflict(error)
  }
}

async function confirm() {
  if (!selected.value) return
  await confirmSchedule(selected.value.id)
  ElMessage.success('预约已确认')
  detailDialog.value = false
  await load()
}

async function reject() {
  if (!selected.value) return
  const { value } = await ElMessageBox.prompt('请输入拒绝原因', '拒绝预约', {
    inputType: 'textarea',
    inputValidator: (text) => Boolean(text?.trim()) || '请填写拒绝原因',
  })
  await rejectSchedule(selected.value.id, value)
  ElMessage.success('预约已拒绝')
  detailDialog.value = false
  await loadOptions()
  await load()
}

async function withdraw() {
  if (!selected.value) return
  await ElMessageBox.confirm('对方尚未确认，确定撤回这条预约吗？', '撤回预约', {
    type: 'warning',
  })
  await withdrawSchedule(selected.value.id)
  ElMessage.success('预约已撤回，项目工时额度已释放')
  detailDialog.value = false
  await loadOptions()
  await load()
}

async function remove() {
  if (!selected.value) return
  await ElMessageBox.confirm('确认取消这条预约吗？记录会保留在历史中。', '取消预约', {
    type: 'warning',
  })
  await deleteSchedule(selected.value.id)
  ElMessage.success('预约已取消并保留历史')
  detailDialog.value = false
  await load()
}

async function dropToSlot(payload: {
  scheduleId: number
  userId: number
  date: string
  time: string
}) {
  const item = schedules.value.find((value) => value.id === payload.scheduleId)
  if (!item || item.user_id !== payload.userId || item.created_by !== userStore.profile?.id) return
  const duration = dayjs(item.end_time).diff(dayjs(item.start_time), 'minute')
  const start = dayjs(`${payload.date} ${payload.time}`)
  try {
    await moveSchedule(item.id, {
      start_time: start.format('YYYY-MM-DD HH:mm:ss'),
      end_time: start.add(duration, 'minute').format('YYYY-MM-DD HH:mm:ss'),
      expected_version: item.version,
    })
    ElMessage.success('预约时间已调整，等待本人重新确认')
    await load()
  } catch (error) {
    showConflict(error)
  }
}

function startMonthDrag(event: DragEvent, item: Schedule) {
  if (
    item.created_by !== userStore.profile?.id
    || !['pending', 'rejected', 'confirmed'].includes(item.status)
  ) return event.preventDefault()
  event.dataTransfer?.setData('schedule-id', String(item.id))
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}

async function dropOnDay(event: DragEvent, date: string) {
  const meta = scheduleDayMeta(date)
  if (meta.kind !== 'workday') return
  event.preventDefault()
  const item = schedules.value.find(
    (value) => value.id === Number(event.dataTransfer?.getData('schedule-id')),
  )
  if (!item) return
  await dropToSlot({
    scheduleId: item.id,
    userId: item.user_id,
    date,
    time: dayjs(item.start_time).format('HH:mm'),
  })
}

function allowMonthDrop(event: DragEvent, date: string) {
  if (scheduleDayMeta(date).kind === 'workday') event.preventDefault()
}

async function openBatch() {
  if (!bookableProjects.value.length) {
    return ElMessage.warning('没有当前权限可预约的已审批项目')
  }
  Object.assign(batchForm, {
    user_ids: [],
    project_id: bookableProjects.value[0].id,
    task_id: 0,
    work_date: anchorDate.value,
    session: 'morning',
    start_clock: '08:30',
    end_clock: '09:30',
    remark: '',
  })
  batchForm.task_id = batchTasks.value[0]?.id || 0
  await loadBatchUsers(batchForm.project_id)
  await loadCalendar(dayjs(batchForm.work_date).year())
  batchDialog.value = true
}

async function saveBatch() {
  if (!batchForm.user_ids.length || !batchForm.project_id || !batchForm.task_id) {
    return ElMessage.warning('请选择人员、项目和任务')
  }
  await loadCalendar(dayjs(batchForm.work_date).year())
  if (!batchDateIsWorkday()) return ElMessage.warning('只能预约工作日，法定节假日不能预约')
  const remaining = bookableProjects.value.find((item) => item.id === batchForm.project_id)?.remaining_hours
  if (remaining !== undefined && batchHours.value * batchForm.user_ids.length > remaining) {
    return ElMessage.warning('项目剩余工时不足，请先申请追加工时并等待 L3 审批')
  }
  batchSaving.value = true
  try {
    const result = await batchCreateSchedules({
      user_ids: batchForm.user_ids,
      project_id: batchForm.project_id,
      task_id: batchForm.task_id,
      start_time: `${batchForm.work_date} ${batchForm.start_clock}:00`,
      end_time: `${batchForm.work_date} ${batchForm.end_clock}:00`,
      planned_hours: batchHours.value,
      remark: batchForm.remark,
    })
    ElMessage.success(`已提交 ${result.created} 条预约，分别等待被预约人确认`)
    batchDialog.value = false
    await loadOptions()
    await load()
  } catch (error) {
    showConflict(error)
  } finally {
    batchSaving.value = false
  }
}

async function copyPreviousWeek() {
  if (viewMode.value !== 'week') return ElMessage.warning('复制周预约前请切换到周视图')
  const target = dayjs(weekDays.value[0])
  const result = await copyScheduleWeek({
    source_week_start: target.subtract(7, 'day').format('YYYY-MM-DD HH:mm:ss'),
    target_week_start: target.format('YYYY-MM-DD HH:mm:ss'),
    user_ids: filter.user_id ? [filter.user_id] : undefined,
  })
  ElMessage.success(`已提交 ${result.created} 条预约，跳过 ${result.skipped.length} 条`)
  await loadOptions()
  await load()
}

watch(
  () => batchForm.session,
  (session) => {
    batchForm.start_clock = session === 'morning' ? '08:30' : '13:00'
    batchForm.end_clock = session === 'morning' ? '09:30' : '14:00'
  },
)
watch(
  () => batchForm.work_date,
  (value) => {
    if (value) loadCalendar(dayjs(value).year())
  },
)
watch(
  () => batchForm.start_clock,
  () => {
    if (!batchEndOptions.value.includes(batchForm.end_clock)) {
      batchForm.end_clock = batchEndOptions.value[0]
    }
  },
)

onMounted(async () => {
  await loadOptions()
  await load()
})
</script>

<template>
  <div class="page-shell">
    <header class="page-header">
      <div>
        <h1 class="page-title">任务共享看板</h1>
        <p class="page-subtitle">每个人都可安排自己的培训、会议、休假、外出或其他时间；个人占用时段不可预约，项目预约由被预约人本人审批。</p>
      </div>
      <div class="header-actions">
        <el-button @click="openMyTimeDrawer">我的时间安排</el-button>
        <template v-if="canBook"><el-button @click="copyPreviousWeek">复制上周</el-button><el-button @click="openBatch">批量预约</el-button><el-button type="primary" @click="openBookingButton">预约人力</el-button></template>
      </div>
    </header>
    <section class="surface board-tools">
      <div class="filters">
        <el-select v-model="filter.project_id" clearable filterable placeholder="项目" style="width:190px"><el-option v-for="item in projects" :key="item.id" :label="item.name" :value="item.id"/></el-select>
        <el-select v-model="filter.user_id" clearable filterable placeholder="人员" style="width:150px"><el-option v-for="item in users" :key="item.id" :label="item.name" :value="item.id"/></el-select>
        <el-select v-model="filter.department_id" clearable placeholder="部门" style="width:150px"><el-option v-for="item in departments" :key="item.id" :label="item.name" :value="item.id"/></el-select>
        <el-select v-model="filter.organization_id" clearable filterable placeholder="组织" style="width:170px"><el-option v-for="item in flatOrganizations" :key="item.id" :label="item.label" :value="item.id"/></el-select>
        <el-input v-model="filter.employee_no" clearable placeholder="工号" style="width:130px"/>
        <el-input v-model="filter.name" clearable placeholder="姓名" style="width:130px"/>
        <el-button @click="applyFilters">查询</el-button>
      </div>
      <div class="date-nav">
        <el-button @click="move(-1)">‹</el-button>
        <el-date-picker v-model="anchorDate" value-format="YYYY-MM-DD" :clearable="false" style="width:140px" @change="load"/>
        <el-button @click="move(1)">›</el-button>
        <el-segmented v-model="viewMode" :options="[{label:'日',value:'day'},{label:'周',value:'week'},{label:'月',value:'month'}]" @change="load"/>
      </div>
    </section>
    <section class="surface board-card" v-loading="loading">
      <div class="board-caption">
        <strong>{{ dateTitle }}</strong>
        <span class="time-legend"><span><i class="legend-work"></i>可用工作时间</span><span><i class="legend-pending"></i>待处理预约</span><span><i class="legend-accepted"></i>已接受预约</span><span><i class="legend-off"></i>午休/非工作时间</span><span><i class="legend-holiday"></i>法定节假日</span><span><i class="legend-personal"></i>个人安排</span></span>
      </div>
      <div v-if="viewMode!=='month'" class="board-scroll">
        <div class="sticky-header">
          <div class="person-head">人员</div>
          <ScheduleTimelineHeader :days="days" :slots="slots" :cell-width="cellWidth" :day-meta="timelineDayMeta"/>
        </div>
        <UserScheduleRow
          v-for="user in visibleUsers"
          :key="user.id"
          :user-id="user.id"
          :user-name="user.id===userStore.profile?.id ? '我的日程' : user.name"
          :days="days"
          :slots="slots"
          :cell-width="cellWidth"
          :schedules="boardSchedules"
          :personal-blocks="personalBlocks"
          :current-user-id="userStore.profile?.id||0"
          :day-meta="timelineDayMeta"
          @blank="handleBlankSlot"
          @booking="openDetail"
          @personal-block="openPersonalBlock"
          @person="openPersonSchedules"
          @drop-booking="dropToSlot"
        />
        <el-empty v-if="!visibleUsers.length" description="没有可展示的人员"/>
      </div>
      <div v-else class="month-grid">
        <div v-for="name in ['一','二','三','四','五','六','日']" :key="name" class="weekday">周{{ name }}</div>
        <div
          v-for="date in monthDays"
          :key="date"
          class="month-day"
          :class="{outside:dayjs(date).month()!==dayjs(anchorDate).month(),today:date===beijingNow().format('YYYY-MM-DD'),weekend:scheduleDayMeta(date).kind==='weekend',holiday:scheduleDayMeta(date).kind==='holiday','adjusted-workday':scheduleDayMeta(date).kind==='workday'&&Boolean(scheduleDayMeta(date).name)}"
          @dragover="allowMonthDrop($event,date)"
          @drop="dropOnDay($event,date)"
          @dblclick="openMonthCreate(date)"
        >
          <div class="month-day-head"><span class="day-number">{{ dayjs(date).date() }}</span><small v-if="scheduleDayMeta(date).kind==='holiday'">{{ scheduleDayMeta(date).name || '法定节假日' }}</small><small v-else-if="scheduleDayMeta(date).kind==='workday'&&scheduleDayMeta(date).name">调休工作日</small></div>
          <button v-for="item in dayPersonalBlocks(date).slice(0,5)" :key="`personal-${item.id}`" class="month-booking month-personal" :class="`personal-${item.time_type}`" @click.stop="openPersonalBlock(item)"><b>{{ dayjs(item.start_time).format('HH:mm') }}</b> {{ item.user_name }} · {{ personalTypeLabel[item.time_type] }}</button>
          <button v-for="item in daySchedules(date).slice(0,Math.max(5-dayPersonalBlocks(date).length,0))" :key="item.id" class="month-booking" :class="`status-${item.status}`" :draggable="item.created_by===userStore.profile?.id&&['pending','confirmed'].includes(item.status)" @dragstart="startMonthDrag($event,item)" @click.stop="openDetail(item)"><b>{{ dayjs(item.start_time).format('HH:mm') }}</b> {{ item.user_name }} · {{ item.task_name }}</button>
          <small v-if="daySchedules(date).length+dayPersonalBlocks(date).length>5">另有 {{ daySchedules(date).length+dayPersonalBlocks(date).length-5 }} 条</small>
        </div>
      </div>
    </section>
    <ScheduleBookingDialog v-model="bookingDialog" :initial="selected" :slot="initialSlot" :projects="bookableProjects" :tasks="tasks" :users="users" @save="save"/>
    <ScheduleConflictDialog v-model="conflictDialog" :conflicts="conflicts"/>
    <PersonalTimeDialog v-model="personalDialog" :slot="personalInitialSlot" @save="savePersonalTime"/>

    <el-drawer v-model="myTimeDrawer" size="720px">
      <template #header><div class="my-time-header"><div><strong>我的时间安排</strong><small>培训、会议、休假、外出等个人占用会阻止其他人重复预约。</small></div><el-button type="primary" @click="openPersonalCreate()">新增安排</el-button></div></template>
      <div class="my-time-filter"><el-select v-model="myTimeQuery.status" clearable placeholder="全部状态" style="width:150px" @change="myTimeQuery.page=1;loadMyTimeBlocks()"><el-option label="生效中" value="active"/><el-option label="已撤回" value="withdrawn"/></el-select></div>
      <el-table v-loading="myTimeLoading" :data="myTimeRows">
        <el-table-column label="状态类型" width="105"><template #default="{row}"><el-tag effect="plain" :type="row.time_type==='leave'?'danger':row.time_type==='meeting'?'warning':'info'">{{ personalTypeLabel[row.time_type] }}</el-tag></template></el-table-column>
        <el-table-column label="时间" width="190"><template #default="{row}"><div class="time-range"><strong>{{ dayjs(row.start_time).format('YYYY-MM-DD') }}</strong><span>{{ dayjs(row.start_time).format('HH:mm') }}–{{ dayjs(row.end_time).format('HH:mm') }} · {{ row.planned_hours }}h</span></div></template></el-table-column>
        <el-table-column prop="remark" label="备注" min-width="150" show-overflow-tooltip><template #default="{row}">{{ row.remark || '—' }}</template></el-table-column>
        <el-table-column label="状态" width="80"><template #default="{row}"><el-tag :type="row.status==='active'?'success':'info'" effect="plain">{{ row.status === 'active' ? '生效中' : '已撤回' }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="80"><template #default="{row}"><el-button v-if="row.status==='active'" link type="warning" @click="withdrawPersonalBlock(row)">撤回</el-button></template></el-table-column>
      </el-table>
      <el-empty v-if="!myTimeLoading&&!myTimeRows.length" description="暂无个人时间安排"/>
      <div v-if="myTimeTotal" class="person-pagination"><el-pagination v-model:current-page="myTimeQuery.page" :page-size="myTimeQuery.page_size" layout="total, prev, pager, next" :total="myTimeTotal" @current-change="loadMyTimeBlocks"/></div>
    </el-drawer>

    <el-drawer v-model="personDrawer" :title="`${selectedPerson?.userName || '人员'}的全部项目时间安排`" size="780px">
      <div class="person-overview">
        <div class="person-summary">
          <span class="overview-avatar">{{ selectedPerson?.userName?.slice(0,1) || '人' }}</span>
          <div><strong>{{ selectedPerson?.userName }}</strong><small>当前权限范围内共 {{ personTotal }} 条项目时间安排，不受看板当前日期窗口限制。</small></div>
        </div>
        <el-select v-model="personQuery.status" clearable placeholder="全部状态" style="width:160px" @change="personQuery.page=1;loadPersonSchedules()">
          <el-option label="待本人确认" value="pending"/><el-option label="变更待确认" value="changed"/><el-option label="已确认" value="confirmed"/><el-option label="进行中" value="running"/><el-option label="已完成" value="completed"/><el-option label="已拒绝" value="rejected"/><el-option label="已撤回" value="withdrawn"/><el-option label="已取消" value="cancelled"/>
        </el-select>
      </div>
      <el-table v-loading="personLoading" :data="personSchedules" class="person-schedule-table">
        <el-table-column label="时间安排" width="180">
          <template #default="{row}"><div class="time-range"><strong>{{ dayjs(row.start_time).format('YYYY-MM-DD') }}</strong><span>{{ dayjs(row.start_time).format('HH:mm') }}–{{ dayjs(row.end_time).format('HH:mm') }}</span></div></template>
        </el-table-column>
        <el-table-column prop="project_name" label="项目" min-width="150" show-overflow-tooltip/>
        <el-table-column prop="task_name" label="任务" min-width="140" show-overflow-tooltip/>
        <el-table-column label="工时" width="70"><template #default="{row}">{{ row.planned_hours }}h</template></el-table-column>
        <el-table-column label="状态" width="110"><template #default="{row}"><el-tag :type="statusTagType[row.status] || 'info'" effect="plain">{{ statusLabel[row.status] || row.status }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="70"><template #default="{row}"><el-button link type="primary" @click="openPersonScheduleDetail(row)">详情</el-button></template></el-table-column>
      </el-table>
      <el-empty v-if="!personLoading&&!personSchedules.length" description="该人员暂无符合条件的项目时间安排"/>
      <div v-if="personTotal" class="person-pagination"><el-pagination v-model:current-page="personQuery.page" :page-size="personQuery.page_size" layout="total, prev, pager, next" :total="personTotal" @current-change="loadPersonSchedules"/></div>
    </el-drawer>

    <el-dialog v-model="personalDetailDialog" title="个人时间安排详情" width="560px">
      <el-descriptions v-if="selectedPersonalBlock" :column="2" border>
        <el-descriptions-item label="人员">{{ selectedPersonalBlock.user_name }}</el-descriptions-item>
        <el-descriptions-item label="时间状态"><el-tag effect="plain">{{ personalTypeLabel[selectedPersonalBlock.time_type] }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="开始">{{ formatDateTime(selectedPersonalBlock.start_time) }}</el-descriptions-item>
        <el-descriptions-item label="结束">{{ formatDateTime(selectedPersonalBlock.end_time) }}</el-descriptions-item>
        <el-descriptions-item label="占用工时">{{ selectedPersonalBlock.planned_hours }}h</el-descriptions-item>
        <el-descriptions-item label="状态">{{ selectedPersonalBlock.status === 'active' ? '生效中' : '已撤回' }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ selectedPersonalBlock.remark || '—' }}</el-descriptions-item>
      </el-descriptions>
      <template #footer><el-button @click="personalDetailDialog=false">关闭</el-button><el-button v-if="selectedPersonalBlock?.user_id===userStore.profile?.id&&selectedPersonalBlock?.status==='active'" type="warning" @click="withdrawPersonalBlock()">撤回安排</el-button></template>
    </el-dialog>

    <el-dialog v-model="batchDialog" title="批量提交人力预约" width="640px">
      <el-alert title="每位被预约人分别审批；总占用工时 = 单人工时 × 人数。" type="info" :closable="false" show-icon/>
      <el-form label-position="top">
        <el-form-item label="预约人员" required><el-select v-model="batchForm.user_ids" multiple filterable collapse-tags placeholder="可选择多位项目成员" style="width:100%"><el-option v-for="item in batchUsers" :key="item.id" :label="item.name" :value="item.id"/></el-select></el-form-item>
        <div class="form-grid">
          <el-form-item label="项目" required><el-select v-model="batchForm.project_id" filterable style="width:100%" @change="changeBatchProject"><el-option v-for="item in bookableProjects" :key="item.id" :label="`${item.name}（剩余 ${item.remaining_hours}h）`" :value="item.id"/></el-select></el-form-item>
          <el-form-item label="任务" required><el-select v-model="batchForm.task_id" filterable style="width:100%"><el-option v-for="item in batchTasks" :key="item.id" :label="item.name" :value="item.id"/></el-select></el-form-item>
          <el-form-item label="工作日期"><el-date-picker v-model="batchForm.work_date" type="date" value-format="YYYY-MM-DD" :disabled-date="disabledBatchDate" style="width:100%"/></el-form-item>
          <el-form-item label="工作时段"><el-radio-group v-model="batchForm.session"><el-radio-button value="morning">上午</el-radio-button><el-radio-button value="afternoon">下午</el-radio-button></el-radio-group></el-form-item>
          <el-form-item label="开始时间"><el-select v-model="batchForm.start_clock" style="width:100%"><el-option v-for="item in batchStartOptions" :key="item" :label="item" :value="item"/></el-select></el-form-item>
          <el-form-item label="结束时间"><el-select v-model="batchForm.end_clock" style="width:100%"><el-option v-for="item in batchEndOptions" :key="item" :label="item" :value="item"/></el-select></el-form-item>
        </div>
        <el-form-item label="自动计算"><el-input :model-value="`单人 ${batchHours}h，共 ${batchHours*batchForm.user_ids.length}h`" disabled/></el-form-item>
        <el-form-item label="备注"><el-input v-model="batchForm.remark" type="textarea" :rows="2"/></el-form-item>
      </el-form>
      <template #footer><el-button @click="batchDialog=false">取消</el-button><el-button type="primary" :loading="batchSaving" @click="saveBatch">预约</el-button></template>
    </el-dialog>

    <el-dialog v-model="detailDialog" title="预约详情" width="600px">
      <el-descriptions v-if="selected" :column="2" border>
        <el-descriptions-item label="人员">{{ selected.user_name }}</el-descriptions-item>
        <el-descriptions-item label="状态"><el-tag>{{ statusLabel[selected.status] || selected.status }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="项目">{{ selected.project_name }}</el-descriptions-item>
        <el-descriptions-item label="任务">{{ selected.task_name }}</el-descriptions-item>
        <el-descriptions-item label="开始">{{ formatDateTime(selected.start_time) }}</el-descriptions-item>
        <el-descriptions-item label="结束">{{ formatDateTime(selected.end_time) }}</el-descriptions-item>
        <el-descriptions-item label="自动工时">{{ selected.planned_hours }}h</el-descriptions-item>
        <el-descriptions-item label="版本">v{{ selected.version }}</el-descriptions-item>
        <el-descriptions-item label="审批规则" :span="2">仅 {{ selected.user_name }} 本人可以同意或拒绝</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ selected.remark || '—' }}</el-descriptions-item>
        <el-descriptions-item v-if="selected.rejection_reason" label="拒绝原因" :span="2">{{ selected.rejection_reason }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button v-if="canEdit" @click="openEdit">编辑</el-button>
        <el-button v-if="canDelete" type="danger" plain @click="remove">删除</el-button>
        <el-button v-if="canWithdraw" type="warning" plain @click="withdraw">撤回预约</el-button>
        <el-button v-if="canDecide" type="danger" plain @click="reject">本人拒绝</el-button>
        <el-button v-if="canDecide" type="success" @click="confirm">本人同意</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.header-actions,.filters,.date-nav{display:flex;align-items:center;gap:10px}.board-tools{display:flex;align-items:center;justify-content:space-between;padding:14px 16px}.board-card{overflow:hidden}.board-caption{display:flex;align-items:center;justify-content:space-between;padding:15px 18px;border-bottom:1px solid #e9edf1;color:#657083;font-size:12px}.time-legend,.time-legend>span{display:flex;align-items:center}.time-legend{gap:16px}.time-legend>span{gap:5px}.time-legend i{display:block;width:15px;height:10px;border:1px solid #dfe4e9;border-radius:3px}.legend-work{background:#fff}.legend-off{background:#e9edf1}.legend-holiday{border-color:#f1cccc!important;background:#fde8e8}.legend-personal{border-color:#cfc2e2!important;background:#eee7f7}.board-scroll{max-height:calc(100vh - 290px);overflow:auto}.sticky-header{position:sticky;top:0;z-index:10;display:flex;width:max-content;min-width:100%;box-shadow:0 2px 6px rgba(39,52,70,.06)}.person-head{position:sticky;left:0;z-index:12;display:grid;width:170px;flex:0 0 170px;place-items:center;border-right:1px solid #e2e6eb;background:#fafbfc;color:#7b8595;font-size:11px}.month-grid{display:grid;grid-template-columns:repeat(7,1fr);max-height:calc(100vh - 290px);overflow:auto}.weekday{position:sticky;top:0;z-index:4;border-right:1px solid #edf0f3;border-bottom:1px solid #e5e9ed;background:#fafbfc;padding:9px;text-align:center;color:#7c8796;font-size:11px}.month-day{min-height:125px;border-right:1px solid #edf0f3;border-bottom:1px solid #edf0f3;padding:7px;background:#fff}.month-day.outside,.month-day.weekend{background:#f2f4f6;color:#9da6b1}.month-day.holiday{background:#fff0f0;color:#a75b5b}.month-day.adjusted-workday{box-shadow:inset 0 3px #79ad8d}.month-day.today .day-number{background:#3d6c98;color:#fff}.month-day-head{display:flex;align-items:center;justify-content:space-between;gap:6px}.month-day-head small{overflow:hidden;color:inherit;font-size:8px;text-overflow:ellipsis;white-space:nowrap}.day-number{display:grid;width:23px;height:23px;flex:0 0 23px;place-items:center;border-radius:7px;font-size:11px}.month-booking{display:block;width:100%;overflow:hidden;margin-top:4px;border:0;border-radius:5px;background:#e5edf5;padding:4px 5px;text-align:left;color:#486987;font-size:9px;text-overflow:ellipsis;white-space:nowrap;cursor:grab}.month-booking b{font-weight:650}.month-personal{cursor:pointer}.month-personal.personal-training{background:#eee7f7;color:#694f85}.month-personal.personal-meeting{background:#f7edd9;color:#806238}.month-personal.personal-leave{background:#f9e2e2;color:#985353}.month-personal.personal-other{background:#e9edf1;color:#596573}.month-day>small{display:block;margin-top:4px;color:#8d98a6;font-size:9px}.my-time-header{display:flex;width:100%;align-items:center;justify-content:space-between;gap:18px}.my-time-header>div{display:flex;min-width:0;flex-direction:column}.my-time-header strong{color:#344256;font-size:15px}.my-time-header small{margin-top:4px;color:#8d98a6;font-size:10px}.my-time-filter{display:flex;justify-content:flex-end;margin-bottom:14px}.person-overview{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:16px;border-radius:12px;background:#f6f8fa;padding:13px 15px}.person-summary{display:flex;min-width:0;align-items:center;gap:11px}.overview-avatar{display:grid;width:38px;height:38px;flex:0 0 38px;place-items:center;border-radius:11px;background:#dde8f2;color:#315f8e;font-size:14px;font-weight:700}.person-summary>div{display:flex;min-width:0;flex-direction:column}.person-summary strong{color:#344256;font-size:13px}.person-summary small{margin-top:4px;color:#8d98a6;font-size:10px}.person-schedule-table{width:100%}.time-range{display:flex;flex-direction:column}.time-range strong{color:#435166;font-size:11px}.time-range span{margin-top:3px;color:#8190a2;font-size:10px}.person-pagination{display:flex;justify-content:flex-end;padding-top:16px}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.month-personal.personal-business_trip{background:#e3f0f7;color:#426b83}
.month-personal.personal-out_of_office{background:#e4f1e8;color:#4f755a}
.time-legend{flex-wrap:wrap;justify-content:flex-end}.legend-pending{border-color:#e4bd70!important;background:#fff0d4}.legend-accepted{border-color:#a9cfb7!important;background:#dff1e6}.month-booking.status-pending,.month-booking.status-changed{border:1px solid #e4bd70;background:#fff0d4;color:#795518}.month-booking.status-confirmed,.month-booking.status-running,.month-booking.status-completed{border:1px solid #a9cfb7;background:#dff1e6;color:#356149}
</style>
