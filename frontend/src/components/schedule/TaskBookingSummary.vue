<script setup lang="ts">
import type { Task } from '@/types/task'
defineProps<{ task: Task; remainingHours: number }>()
</script>

<template>
  <div class="task-booking-summary" role="status">
    <strong>任务周期：{{ task.planned_start.slice(0, 10) }} 至 {{ task.planned_end.slice(0, 10) }}</strong>
    <span>计划 {{ task.estimated_hours }}h · 本次可预约 {{ remainingHours }}h</span>
    <small>所有成员共享任务额度，待确认预约也预占额度；预约日期须在任务周期内。</small>
  </div>
</template>

<style scoped>
.task-booking-summary{display:flex;flex-direction:column;gap:5px;padding:12px 14px;margin-bottom:18px;border:1px solid var(--el-border-color-light);border-radius:8px;background:var(--el-fill-color-light);font-size:13px;color:var(--el-text-color-regular)}
.task-booking-summary strong{font-weight:600;color:var(--el-text-color-primary)}
.task-booking-summary small{font-size:12px;color:var(--el-text-color-secondary);line-height:1.5}
</style>
