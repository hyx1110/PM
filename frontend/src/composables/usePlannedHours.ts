import { computed, onScopeDispose, ref, watch } from 'vue'
import { getPlannedHours, type PlannedHoursEstimate } from '@/api/work-calendar'

/** Creation defaults only; never rewrite persisted plans or manual overrides. */
export function usePlannedHours(options: {
  enabled: () => boolean
  start: () => string
  end: () => string
  members: () => number[]
  getHours: () => number
  setHours: (value: number) => void
}) {
  const estimate = ref<PlannedHoursEstimate>()
  const loading = ref(false)
  const manual = ref(false)
  const error = ref('')
  let generation = 0
  let timer: ReturnType<typeof setTimeout> | undefined
  const input = computed({
    get: options.getHours,
    set: (value: number | undefined) => {
      manual.value = true
      options.setHours(value ?? Number.NaN)
    },
  })
  watch(
    () => [options.enabled(), options.start(), options.end(), new Set(options.members().filter(Boolean)).size] as const,
    ([enabled, start, end, memberCount]) => {
      const current = ++generation
      clearTimeout(timer)
      estimate.value = undefined
      loading.value = false
      error.value = ''
      if (!enabled || !start || !end || end < start || !memberCount) return
      loading.value = true
      timer = setTimeout(async () => {
        try {
          const result = await getPlannedHours(start, end, memberCount)
          if (current !== generation) return
          estimate.value = result
          if (!manual.value) options.setHours(result.planned_hours)
        } catch {
          if (current === generation) error.value = '工作日历读取失败，请重新选择日期，或手动填写工时。'
        } finally {
          if (current === generation) loading.value = false
        }
      }, 250)
    },
    { immediate: true, flush: 'sync' },
  )
  function useDefault() {
    manual.value = false
    if (estimate.value) options.setHours(estimate.value.planned_hours)
  }
  function reset() {
    manual.value = false
    estimate.value = undefined
  }
  onScopeDispose(() => { generation++; clearTimeout(timer) })
  return { input, estimate, loading, manual, error, reset, useDefault }
}
