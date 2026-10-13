<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  startDate: string
  endDate: string
}>()

const emit = defineEmits<{
  'update:startDate': [value: string]
  'update:endDate': [value: string]
  change: []
}>()

// Keep existing API fields and quick-date buttons in sync with the single picker.
const range = computed<[string, string] | null>({
  get: (): [string, string] | null => props.startDate && props.endDate ? [props.startDate, props.endDate] : null,
  set: (value: [string, string] | null) => {
    emit('update:startDate', value?.[0] || '')
    emit('update:endDate', value?.[1] || '')
    emit('change')
  },
})
</script>

<template>
  <div class="date-range-filter">
    <el-date-picker
      v-model="range"
      type="daterange"
      value-format="YYYY-MM-DD"
      format="YYYY-MM-DD"
      start-placeholder="开始日期"
      end-placeholder="结束日期"
      range-separator="至"
      aria-label="时间段"
      title="时间段"
      clearable
      unlink-panels
    />
  </div>
</template>

<style scoped>
.date-range-filter {
  width: 250px;
  max-width: 100%;
  flex: 0 0 auto;
}

.date-range-filter :deep(.el-date-editor) {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  box-sizing: border-box;
  flex: none;
}
</style>
