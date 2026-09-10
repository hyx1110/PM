<script setup lang="ts">
import dayjs from 'dayjs'
import type { ScheduleConflict } from '@/types/schedule'
defineProps<{modelValue:boolean;conflicts:ScheduleConflict[]}>()
defineEmits<{ 'update:modelValue':[value:boolean] }>()
</script>

<template>
  <el-dialog :model-value="modelValue" title="检测到人力时间冲突" width="760px" @update:model-value="$emit('update:modelValue',$event)">
    <el-alert type="error" :closable="false" show-icon title="当前预约与以下有效排期重叠，V1.0 不允许直接保存。"/>
    <el-table :data="conflicts" class="conflict-table"><el-table-column prop="user_name" label="冲突人员" width="100"/><el-table-column prop="project_name" label="冲突项目" min-width="150"/><el-table-column prop="task_name" label="冲突任务" min-width="150"/><el-table-column label="冲突时间" width="270"><template #default="{row}">{{dayjs(row.start_time).format('YYYY-MM-DD HH:mm')}} 至 {{dayjs(row.end_time).format('YYYY-MM-DD HH:mm')}}</template></el-table-column></el-table>
    <template #footer><el-button type="primary" @click="$emit('update:modelValue',false)">返回修改</el-button></template>
  </el-dialog>
</template>

<style scoped>.conflict-table{margin-top:18px}</style>

