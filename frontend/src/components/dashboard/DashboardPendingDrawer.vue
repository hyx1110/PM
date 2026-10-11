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
.inbox-summary { display: flex; flex-shrink: 0; justify-content: flex-end; }
.inbox-summary .el-button { flex-shrink: 0; }
.pending-drawer-body > .el-alert { flex-shrink: 0; }
.inbox-list { flex: 1; min-height: 0; }
</style>
