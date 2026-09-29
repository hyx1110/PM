<script setup lang="ts">
import { computed, ref } from 'vue'
import dayjs from 'dayjs'
import { Calendar, Collection } from '@element-plus/icons-vue'
import type { DashboardPendingItem, DashboardTaskItem, DashboardWorkbench } from '@/types/report'

const props = defineProps<{
  overview: DashboardWorkbench['overview']
  pendingItems: DashboardPendingItem[]
  tasks: DashboardTaskItem[]
}>()
const emit = defineEmits<{ pending: [item: DashboardPendingItem]; task: [item: DashboardTaskItem] }>()
const tab = ref<'all' | 'action' | 'task'>('all')
const statusLabels: Record<string, string> = { not_started: '未开始', running: '进行中', delayed: '已逾期' }
const timestamp = (value?: string | null) => value && dayjs(value).isValid() ? dayjs(value).valueOf() : Number.MAX_SAFE_INTEGER
interface Row {
  id: string; title: string; meta: string; status: string; time: string; sortTime: number
  action?: DashboardPendingItem; task?: DashboardTaskItem
}
const rows = computed<Row[]>(() => {
  const actions: Row[] = props.pendingItems.map(item => {
    const time = item.start_time || item.created_at
    return {
      id: item.id, title: item.title, meta: `${item.type_label} · ${item.project_name || '未关联项目'} · ${item.applicant_name}`,
      status: item.type === 'booking' ? '待确认' : '待审批',
      time: time && dayjs(time).isValid() ? dayjs(time).format('MM/DD HH:mm') : '时间未记录',
      sortTime: timestamp(time), action: item,
    }
  })
  const tasks: Row[] = props.tasks.filter(item => item.status !== 'completed').map(item => ({
    id: `task-${item.id}`, title: item.name, meta: `我的任务 · ${item.project_name}`,
    status: statusLabels[item.status] || item.status, time: `${dayjs(item.planned_end).format('MM/DD')} 截止`,
    sortTime: timestamp(item.planned_end), task: item,
  }))
  return (tab.value === 'action' ? actions : tab.value === 'task' ? tasks : [...actions, ...tasks])
    .sort((a, b) => a.sortTime - b.sortTime || a.id.localeCompare(b.id))
})
const total = computed(() => tab.value === 'action' ? props.overview.pending_action_count : tab.value === 'task' ? props.overview.pending_task_count : props.overview.pending_count)
function open(row: Row) {
  if (row.action) emit('pending', row.action)
  else if (row.task) emit('task', row.task)
}
</script>

<template>
  <section class="surface pending-card">
    <header><h2>待处理事项</h2><p>审批、预约确认与我的未完成任务。</p></header>
    <nav class="pending-tabs" aria-label="待办分类">
      <button :class="{active:tab==='all'}" :aria-pressed="tab==='all'" @click="tab='all'">全部</button>
      <button :class="{active:tab==='action'}" :aria-pressed="tab==='action'" @click="tab='action'">审批 / 预约</button>
      <button :class="{active:tab==='task'}" :aria-pressed="tab==='task'" @click="tab='task'">我的任务</button>
    </nav>
    <div v-if="rows.length" class="pending-list" tabindex="0" role="region" aria-label="待处理事项列表，可滚动查看">
      <el-tooltip v-for="row in rows" :key="row.id" :content="`${row.title} · ${row.meta} · ${row.time} · ${row.status}`" :show-after="350" placement="top">
        <button class="pending-row" @click="open(row)">
          <span class="row-icon" :class="{task:row.task}"><el-icon><Collection v-if="row.task" /><Calendar v-else /></el-icon></span>
          <span class="row-main"><strong>{{row.title}}</strong><small>{{row.meta}}</small><span class="row-meta"><time>{{row.time}}</time><span :class="{delayed:row.task?.status==='delayed'}">{{row.status}}</span></span></span>
        </button>
      </el-tooltip>
    </div>
    <div v-else class="compact-empty">{{total ? '当前摘要暂无条目，请进入对应模块查看' : '当前没有需要处理的内容'}}</div>
    <footer>已展示 {{rows.length}} / {{total}} 项<span>{{rows.length < total ? ' · 更多内容见对应业务模块' : ' · 点击查看与处理'}}</span></footer>
  </section>
</template>

<style scoped>
.pending-card { display: flex; min-width: 0; min-height: 0; flex-direction: column; overflow: hidden; padding: 24px; }
header,nav,footer { flex-shrink: 0; }
h2 { margin: 0; color: #1f2f43; font-size: 20px; font-weight: 650; line-height: 1.5; }
header p { margin: 8px 0 0; color: #6f7f92; font-size: 14px; line-height: 1.6; }
.pending-tabs { display: flex; gap: 4px; margin: 18px 0 8px; padding: 4px; border: 1px solid #e7ecf1; border-radius: 9px; background: #f4f6f8; }
.pending-tabs button { flex: 1; min-height: 34px; border: 0; border-radius: 6px; background: transparent; padding: 6px; color: #5d7088; font-size: 13px; cursor: pointer; white-space: nowrap; }
.pending-tabs button.active { background: #fff; color: #2f628f; font-weight: 600; box-shadow: 0 1px 5px #314c6714; }
.pending-list { min-height: 0; flex: 1; overflow: auto; overscroll-behavior: contain; scrollbar-gutter: stable; }
.pending-row { display: flex; align-items: flex-start; gap: 12px; width: 100%; padding: 14px 4px; border: 0; border-bottom: 1px solid #e9edf2; background: transparent; text-align: left; cursor: pointer; }
.pending-row:hover { background: #f5f8fb; border-radius: 8px; }
.row-icon { display: grid; flex: 0 0 32px; height: 32px; place-items: center; border-radius: 9px; background: #faf2e5; color: #936a32; font-size: 17px; }
.row-icon.task { background: #eaf2f8; color: #47749c; }
.row-main { display: flex; min-width: 0; flex: 1; flex-direction: column; gap: 5px; }
.row-main strong { color: #2d3e52; font-size: 15px; font-weight: 600; overflow-wrap: anywhere; }
.row-main small { overflow: hidden; color: #6d7e91; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.row-meta { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px; color: #62788c; font-size: 12px; }
.row-meta .delayed { color: #ad5651; }
.compact-empty { display: grid; flex: 1; place-items: center; padding: 16px; color: #708095; font-size: 14px; text-align: center; }
footer { border-top: 1px solid #edf1f4; padding-top: 12px; color: #748396; font-size: 12px; }
button:focus-visible,.pending-list:focus-visible { outline: 2px solid #527fa6; outline-offset: -2px; }
@media(max-width:1440px) { .pending-card { padding: 20px; } }
</style>
