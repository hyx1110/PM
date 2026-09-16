<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { getWorkCalendar } from '@/api/work-calendar'
import type { PersonalTimePayload, PersonalTimeType } from '@/types/personal-time'
import type { WorkCalendarDay } from '@/types/work-calendar'
import { beijingNow } from '@/utils/time'

const props = defineProps<{
  modelValue: boolean
  slot?: { date: string; time: string }
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  save: [payload: PersonalTimePayload]
}>()

const formRef = ref<FormInstance>()
const calendar = ref<WorkCalendarDay[]>([])
const loadedYears = new Set<number>()
const form = reactive({
  time_type: 'meeting' as PersonalTimeType,
  work_date: '',
  session: 'morning' as 'morning' | 'afternoon',
  start_clock: '08:30',
  end_clock: '09:30',
  remark: '',
})
const rules: FormRules = {
  time_type: [{ required: true, message: '请选择时间状态' }],
  work_date: [{ required: true, message: '请选择工作日期' }],
}
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

async function ensureCalendar(year: number) {
  if (!year || loadedYears.has(year)) return
  const items = await getWorkCalendar(year)
  calendar.value = [
    ...calendar.value.filter((item) => dayjs(item.work_date).year() !== year),
    ...items,
  ]
  loadedYears.add(year)
}

function isValidWorkday(date: string) {
  const override = calendar.value.find((item) => item.work_date === date)
  if (override) return override.day_type === 'workday'
  return ![0, 6].includes(dayjs(date).day())
}

function disabledDate(value: Date) {
  const date = dayjs(value).format('YYYY-MM-DD')
  const override = calendar.value.find((item) => item.work_date === date)
  if (override) return override.day_type === 'holiday'
  return [0, 6].includes(dayjs(value).day())
}

function resetSessionTimes() {
  form.start_clock = form.session === 'morning' ? '08:30' : '13:00'
  form.end_clock = form.session === 'morning' ? '09:30' : '14:00'
}

watch(
  () => props.modelValue,
  async (visible) => {
    if (!visible) return
    const date = props.slot?.date || beijingNow().format('YYYY-MM-DD')
    const clock = props.slot?.time || '08:30'
    const session = clock < '12:00' ? 'morning' : 'afternoon'
    const limit = session === 'morning' ? '12:00' : '17:30'
    const suggestedEnd = dayjs(`2000-01-01 ${clock}`).add(60, 'minute').format('HH:mm')
    Object.assign(form, {
      time_type: 'meeting',
      work_date: date,
      session,
      start_clock: clock,
      end_clock: suggestedEnd > limit ? limit : suggestedEnd,
      remark: '',
    })
    await ensureCalendar(dayjs(date).year())
  },
  { immediate: true },
)

watch(
  () => form.work_date,
  (value) => {
    if (value) ensureCalendar(dayjs(value).year())
  },
)

watch(
  () => form.start_clock,
  () => {
    if (!endOptions.value.includes(form.end_clock)) {
      form.end_clock = endOptions.value[0] || sessionEnd.value
    }
  },
)

async function submit() {
  if (!(await formRef.value?.validate())) return
  if (!isValidWorkday(form.work_date)) {
    return ElMessage.warning('个人时间只能设置在工作日，法定节假日不能设置')
  }
  if (plannedHours.value <= 0) return ElMessage.warning('请选择有效时间段')
  emit('save', {
    time_type: form.time_type,
    start_time: `${form.work_date} ${form.start_clock}:00`,
    end_time: `${form.work_date} ${form.end_clock}:00`,
    remark: form.remark.trim() || undefined,
  })
}
</script>

<template>
  <el-dialog :model-value="modelValue" title="安排我的时间" width="600px" destroy-on-close @update:model-value="emit('update:modelValue',$event)">
    <el-alert title="保存后该时段将被占用，项目经理不能再预约；你可以随时从“我的时间安排”中撤回。" type="info" :closable="false" show-icon/>
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
      <div class="form-grid">
        <el-form-item label="时间状态" prop="time_type"><el-select v-model="form.time_type" style="width:100%"><el-option label="培训" value="training"/><el-option label="会议" value="meeting"/><el-option label="休假" value="leave"/><el-option label="外出" value="out_of_office"/><el-option label="出差" value="business_trip"/><el-option label="其他安排" value="other"/></el-select></el-form-item>
        <el-form-item label="占用工时"><el-input :model-value="`${plannedHours} 小时`" disabled/></el-form-item>
        <el-form-item label="工作日期" prop="work_date"><el-date-picker v-model="form.work_date" type="date" value-format="YYYY-MM-DD" :disabled-date="disabledDate" style="width:100%"/></el-form-item>
        <el-form-item label="工作时段"><el-radio-group v-model="form.session" @change="resetSessionTimes"><el-radio-button value="morning">上午</el-radio-button><el-radio-button value="afternoon">下午</el-radio-button></el-radio-group></el-form-item>
        <el-form-item label="开始时间"><el-select v-model="form.start_clock" style="width:100%"><el-option v-for="item in startOptions" :key="item" :label="item" :value="item"/></el-select></el-form-item>
        <el-form-item label="结束时间"><el-select v-model="form.end_clock" style="width:100%"><el-option v-for="item in endOptions" :key="item" :label="item" :value="item"/></el-select></el-form-item>
      </div>
      <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="3" maxlength="1000" show-word-limit/></el-form-item>
    </el-form>
    <template #footer><el-button @click="emit('update:modelValue',false)">取消</el-button><el-button type="primary" @click="submit">保存时间安排</el-button></template>
  </el-dialog>
</template>

<style scoped>
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 18px}
</style>
