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
    status: '待确认', sortTime: dayjs(item.created_at || item.start_time).valueOf(), pendingItem: item,
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
  <el-popover trigger="hover" placement="bottom" :width="500" :show-after="140" :hide-after="220" popper-class="dashboard-pending-popper">
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
      <footer><span>悬停快速查看，点击条目可打开详情</span></footer>
    </section>
  </el-popover>
</template>

<style scoped>
.pending-popover{margin:-3px -2px -6px}.pending-popover header{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;border-bottom:1px solid #e6ebf0;padding:3px 3px 13px}.pending-popover header>div{display:flex;flex-direction:column}.pending-popover header strong{color:#24364b;font-size:14px;font-weight:680}.pending-popover header span{margin-top:4px;color:#7f8d9e;font-size:9px}.pending-popover nav{display:flex;border:1px solid #e7ecf1;border-radius:9px;background:#f4f6f8;padding:3px}.pending-popover nav button{border:0;border-radius:6px;background:transparent;padding:6px 8px;color:#718095;font-size:8px;white-space:nowrap;cursor:pointer}.pending-popover nav button.active{background:#fff;color:#2f628f;font-weight:650;box-shadow:0 2px 8px rgba(49,76,103,.1)}.popover-list{display:flex;flex-direction:column}.popover-row{display:grid;width:100%;grid-template-columns:31px minmax(0,1fr) 72px;align-items:center;gap:10px;border:0;border-bottom:1px solid #e9edf2;background:transparent;padding:10px 4px;text-align:left;cursor:pointer;transition:background .15s}.popover-row:hover{border-radius:8px;background:#f5f8fb}.row-icon{display:grid;width:30px;height:30px;place-items:center;border-radius:9px;background:#faf2e5;color:#936a32}.row-icon.task{background:#eaf2f8;color:#47749c}.row-main,.row-side{display:flex;min-width:0;flex-direction:column}.row-main strong,.row-main small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.row-main strong{color:#2d3e52;font-size:10px;font-weight:650}.row-main small{margin-top:4px;color:#8491a0;font-size:8px}.row-side{align-items:flex-end}.row-side strong{color:#536479;font-size:9px;font-weight:600}.row-side small{margin-top:4px;color:#8e99a7;font-size:8px}.row-side small.delayed{color:#ad5651}.row-side small.running{color:#47749c}.popover-empty{display:grid;height:132px;place-items:center;color:#8d99a7;font-size:10px}.pending-popover footer{padding:10px 3px 1px;color:#929ca8;font-size:8px;text-align:right}
</style>
