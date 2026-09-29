<script setup lang="ts">
import type { PlannedHoursEstimate } from '@/api/work-calendar'
defineProps<{ estimate?: PlannedHoursEstimate; loading: boolean; manual: boolean; error: string; includesManager?: boolean }>()
defineEmits<{ reset: [] }>()
</script>

<template>
  <div class="planned-hours-hint" aria-live="polite">
    <span v-if="loading">正在按工作日历计算默认工时…</span>
    <span v-else-if="error">{{ error }}</span>
    <template v-else-if="estimate">
      <span>默认 {{ estimate.workdays }} 个工作日 × {{ estimate.member_count }} 人{{ includesManager ? '（含项目经理）' : '' }} × 8h = {{ estimate.planned_hours }}h。</span>
      <span v-if="!estimate.workdays" class="warning">所选周期没有工作日，请调整日期或按业务需要手动填写。</span>
      <template v-if="manual"><span>已保留手动工时。</span><el-button link type="primary" @click="$emit('reset')">使用默认值</el-button></template>
      <span v-else>可手动调整。</span>
    </template>
    <span v-else>选择日期与成员后，按工作日天数 × 成员人数 × 8h 自动计算；可手动调整。</span>
  </div>
</template>

<style scoped>
.planned-hours-hint{display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px;margin:0 0 16px;color:var(--el-text-color-secondary);font-size:12px;line-height:1.8}.warning{color:var(--el-color-warning)}
</style>
