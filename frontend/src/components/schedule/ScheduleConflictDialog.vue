<script setup lang="ts">
import dayjs from 'dayjs'
import type { ScheduleConflict } from '@/types/schedule'
defineProps<{modelValue:boolean;conflicts:ScheduleConflict[]}>()
defineEmits<{ 'update:modelValue':[value:boolean] }>()
</script>

<template>
  <el-dialog :model-value="modelValue" title="检测到人力时间冲突" width="760px" @update:model-value="$emit('update:modelValue',$event)">
    <el-alert type="error" :closable="false" show-icon title="所选时间与以下项目预约或个人安排重叠，请调整后再保存。"/>
    <el-table :data="conflicts" class="conflict-table"><el-table-column prop="user_name" label="冲突人员" width="100"/><el-table-column label="安排类型" width="110"><template #default="{row}"><el-tag :type="row.conflict_type==='personal_time'?'warning':'info'" effect="plain">{{ row.conflict_type === 'personal_time' ? '个人安排' : '项目预约' }}</el-tag></template></el-table-column><el-table-column prop="project_name" label="项目/来源" min-width="140"/><el-table-column prop="task_name" label="任务/状态" min-width="130"/><el-table-column label="冲突时间" width="250"><template #default="{row}">{{dayjs(row.start_time).format('YYYY-MM-DD HH:mm')}} 至 {{dayjs(row.end_time).format('HH:mm')}}</template></el-table-column></el-table>
    <template #footer><el-button type="primary" @click="$emit('update:modelValue',false)">返回修改</el-button></template>
  </el-dialog>
</template>

<style scoped>.conflict-table{margin-top:18px}</style>
