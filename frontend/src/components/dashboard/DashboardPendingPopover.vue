<script setup lang="ts">
import { computed, ref } from 'vue'
import dayjs from 'dayjs'
import { Calendar, Collection } from '@element-plus/icons-vue'
import type { DashboardPendingItem, DashboardTaskItem, DashboardWorkbench } from '@/types/report'

interface PopoverRow {
  kind: 'action' | 'task'
  id: string
  title: string
  meta: string
  time: string
  status: string
  sortTime: number
  pendingItem?: DashboardPendingItem
  taskItem?: DashboardTaskItem
}

const props = defineProps<{
  overview: DashboardWorkbench['overview']
  pendingItems: DashboardPendingItem[]
  tasks: DashboardTaskItem[]
}>()
const emit = defineEmits<{ pending: [item: DashboardPendingItem]; task: [item: DashboardTaskItem] }>()
const tab = ref<'all' | 'action' | 'task'>('all')
const taskStatusLabel: Record<string, string> = { not_started: '未开始', running: '进行中', delayed: '已逾期' }
const openTasks = computed(() => props.tasks.filter(item => item.status !== 'completed'))
const rows = computed<PopoverRow[]>(() => {
  const actions: PopoverRow[] = props.pendingItems.map(item => ({
    kind: 'action', id: item.id, title: item.title,
    meta: `${item.type_label} · ${item.project_name || '未关联项目'} · ${item.applicant_name}`,
    time: dayjs(item.start_time || item.created_at).format('MM/DD HH:mm'),
    status: item.type === 'booking' ? '待确认' : '待审批', sortTime: dayjs(item.created_at || item.start_time).valueOf(), pendingItem: item,
  }))
  const tasks: PopoverRow[] = openTasks.value.map(item => ({
    kind: 'task', id: `task-${item.id}`, title: item.name,
    meta: `我的任务 · ${item.project_name} · ${item.owner_name}`,
    time: dayjs(item.planned_end).format('MM/DD'),
    status: taskStatusLabel[item.status] || item.status,
    sortTime: dayjs(item.planned_end).valueOf(), taskItem: item,
  }))
  if (tab.value === 'action') return actions.slice(0, 7)
  if (tab.value === 'task') return tasks.slice(0, 7)
  return [...actions, ...tasks].sort((left, right) => left.sortTime - right.sortTime).slice(0, 7)
})
function selectRow(row: PopoverRow) {
  if (row.pendingItem) emit('pending', row.pendingItem)
  else if (row.taskItem) emit('task', row.taskItem)
}
</script>

<template>
  <el-popover trigger="hover" placement="bottom" :width="620" :popper-style="{maxWidth:'calc(100vw - 32px)'}" :show-after="140" :hide-after="220" popper-class="dashboard-pending-popper">
    <template #reference><slot /></template>
    <section class="pending-popover">
      <header><div><strong>待处理事项</strong><span>审批、预约和我的未完成任务</span></div><nav><button :class="{active:tab==='all'}" @click="tab='all'">全部 {{overview.pending_count}}</button><button :class="{active:tab==='action'}" @click="tab='action'">审批/预约 {{overview.pending_action_count}}</button><button :class="{active:tab==='task'}" @click="tab='task'">任务 {{overview.pending_task_count}}</button></nav></header>
      <div v-if="rows.length" class="popover-list">
        <button v-for="row in rows" :key="row.id" class="popover-row" @click="selectRow(row)">
          <span class="row-icon" :class="row.kind"><el-icon><Calendar v-if="row.kind==='action'"/><Collection v-else/></el-icon></span>
          <span class="row-main"><strong>{{row.title}}</strong><small>{{row.meta}}</small></span>
          <span class="row-side"><strong>{{row.time}}</strong><small :class="row.taskItem?.status">{{row.status}}</small></span>
        </button>
      </div>
      <div v-else class="popover-empty">当前没有需要处理的内容</div>
      <footer><span>最多预览 7 项 · 点击条目可查看详情并处理</span></footer>
    </section>
  </el-popover>
</template>

<style scoped>
.pending-popover { padding: 8px; }
.pending-popover header { display: flex; flex-direction: column; gap: 16px; border-bottom: 1px solid #e6ebf0; padding-bottom: 16px; }
.pending-popover header > div { display: flex; flex-direction: column; gap: 6px; }
.pending-popover header strong { color: #24364b; font-size: 18px; font-weight: 650; }
.pending-popover header span { color: #6d7e91; font-size: 13px; }
.pending-popover nav { display: flex; flex-wrap: wrap; gap: 4px; border: 1px solid #e7ecf1; border-radius: 9px; background: #f4f6f8; padding: 4px; }
.pending-popover nav button { flex: 1; min-height: 36px; border: 0; border-radius: 6px; background: transparent; padding: 7px 10px; color: #5d7088; font-size: 13px; white-space: nowrap; cursor: pointer; }
.pending-popover nav button.active { background: #fff; color: #2f628f; font-weight: 600; box-shadow: 0 1px 5px rgba(49,76,103,.08); }
.popover-list { display: flex; max-height: min(400px,45vh); overflow-y: auto; flex-direction: column; overscroll-behavior: contain; }
.popover-row { display: grid; width: 100%; grid-template-columns: 36px minmax(0,1fr) 94px; align-items: center; gap: 14px; border: 0; border-bottom: 1px solid #e9edf2; background: transparent; padding: 16px 4px; text-align: left; cursor: pointer; }
.popover-row:hover { border-radius: 8px; background: #f5f8fb; }
.row-icon { display: grid; width: 36px; height: 36px; place-items: center; border-radius: 10px; background: #faf2e5; color: #936a32; font-size: 18px; }
.row-icon.task { background: #eaf2f8; color: #47749c; }
.row-main,.row-side { display: flex; min-width: 0; flex-direction: column; gap: 6px; }
.row-main strong { color: #2d3e52; font-size: 14px; font-weight: 600; line-height: 1.5; overflow-wrap: anywhere; }
.row-main small { color: #6d7e91; font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.row-side { align-items: flex-end; }
.row-side strong { color: #4d637c; font-size: 13px; font-weight: 500; white-space: nowrap; }
.row-side small { color: #697c91; font-size: 12px; }
.row-side small.delayed { color: #ad5651; }
.row-side small.running { color: #47749c; }
.popover-empty { display: grid; min-height: 110px; place-items: center; color: #708095; font-size: 14px; }
.pending-popover footer { padding-top: 14px; color: #708095; font-size: 12px; text-align: right; line-height: 1.5; }
button:focus-visible { outline: 2px solid #527fa6; outline-offset: -2px; }
</style>
