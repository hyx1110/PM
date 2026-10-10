<script setup lang="ts">
import DashboardPendingPanel from './DashboardPendingPanel.vue'
import type { DashboardPendingItem, DashboardTaskItem, DashboardWorkbench } from '@/types/report'

const visible = defineModel<boolean>({ required: true })
defineProps<{
  overview: DashboardWorkbench['overview']
  pendingItems: DashboardPendingItem[]
  tasks: DashboardTaskItem[]
  loading: boolean
  failed: boolean
}>()
const emit = defineEmits<{
  pending: [item: DashboardPendingItem]
  task: [item: DashboardTaskItem]
  refresh: []
}>()
</script>

<template>
  <el-drawer v-model="visible" title="待处理事项" direction="rtl" size="min(640px, 100vw)" append-to-body destroy-on-close>
    <div class="pending-drawer-body">
      <div class="inbox-summary">
        <p>审批、预约确认与我的未完成任务。点击事项查看详情并处理。</p>
        <el-button :loading="loading" plain @click="emit('refresh')">刷新</el-button>
      </div>
      <el-alert v-if="failed" title="刷新失败，当前列表可能不是最新数据，请重试。" type="warning" :closable="false" show-icon />
      <DashboardPendingPanel
        class="inbox-list" embedded :overview="overview" :pending-items="pendingItems" :tasks="tasks"
        @pending="emit('pending',$event)" @task="emit('task',$event)"
      />
    </div>
    <template #footer><el-button @click="visible=false">关闭</el-button></template>
  </el-drawer>
</template>

<style scoped>
.pending-drawer-body { display: flex; height: 100%; min-height: 0; flex-direction: column; gap: 16px; }
.inbox-summary { display: flex; flex-shrink: 0; align-items: flex-start; justify-content: space-between; gap: 16px; }
.inbox-summary p { margin: 0; color: #6f7f92; font-size: 14px; line-height: 1.7; }
.inbox-summary .el-button { flex-shrink: 0; }
.pending-drawer-body > .el-alert { flex-shrink: 0; }
.inbox-list { flex: 1; min-height: 0; }
</style>
