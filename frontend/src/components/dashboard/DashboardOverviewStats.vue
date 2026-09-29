<script setup lang="ts">
import { computed } from 'vue'
import { Calendar, Collection, TrendCharts, Warning } from '@element-plus/icons-vue'
import DashboardPendingPopover from '@/components/dashboard/DashboardPendingPopover.vue'
import type { DashboardPendingItem, DashboardTaskItem, DashboardWorkbench } from '@/types/report'

const props = defineProps<{
  overview: DashboardWorkbench['overview']
  pendingItems: DashboardPendingItem[]
  tasks: DashboardTaskItem[]
}>()
const emit = defineEmits<{
  open: [target: 'projects' | 'tasks' | 'pending' | 'risks']
  pending: [item: DashboardPendingItem]
  task: [item: DashboardTaskItem]
}>()

const cards = computed(() => [
  {
    key: 'pending' as const,
    label: '待处理事项',
    value: props.overview.pending_count,
    note: `${props.overview.pending_action_count} 审批/预约 · ${props.overview.pending_task_count} 项任务`,
    details: '',
    icon: Calendar,
    tone: 'amber',
  },
  {
    key: 'projects' as const,
    label: '进行中项目',
    value: props.overview.running_projects,
    note: `${props.overview.due_this_week} 个将在 7 天内到期`,
    details: `当前权限范围内共有 ${props.overview.running_projects} 个进行中项目，其中 ${props.overview.due_this_week} 个计划在未来 7 天内结束。`,
    icon: Collection,
    tone: 'blue',
  },
  {
    key: 'tasks' as const,
    label: '任务完成率',
    value: `${props.overview.task_completion_rate}%`,
    note: `${props.overview.completed_tasks} / ${props.overview.total_tasks} 个任务`,
    details: `按当前账号可见任务统计，已完成 ${props.overview.completed_tasks} 个，共 ${props.overview.total_tasks} 个。`,
    icon: TrendCharts,
    tone: 'green',
  },
  {
    key: 'risks' as const,
    label: '需要关注',
    value: props.overview.risk_projects,
    note: `${props.overview.delayed_projects} 延期 · ${props.overview.overrun_tasks} 工时异常`,
    details: `风险项目综合项目延期、任务延期和实际工时超出预计工时计算。`,
    icon: Warning,
    tone: 'red',
  },
])
</script>

<template>
  <section class="overview-grid" aria-label="核心概览">
    <template v-for="card in cards" :key="card.key">
      <DashboardPendingPopover v-if="card.key==='pending'" :overview="overview" :pending-items="pendingItems" :tasks="tasks" @pending="emit('pending',$event)" @task="emit('task',$event)">
        <article class="surface overview-card tone-amber pending-card" tabindex="0">
          <span v-if="overview.pending_count" class="attention-badge">{{overview.pending_count>99?'99+':overview.pending_count}}</span>
          <div class="overview-icon"><el-icon><component :is="card.icon" /></el-icon></div>
          <div class="overview-copy"><span>{{card.label}}</span><strong>{{card.value}}</strong><small>{{card.note}}</small></div>
          <span class="overview-link always">悬停查看</span>
        </article>
      </DashboardPendingPopover>
      <el-tooltip v-else :content="card.details" placement="bottom" :show-after="260">
        <article class="surface overview-card" :class="`tone-${card.tone}`" role="button" tabindex="0" @click="emit('open',card.key)" @keydown.enter="emit('open',card.key)">
          <div class="overview-icon"><el-icon><component :is="card.icon" /></el-icon></div>
          <div class="overview-copy"><span>{{card.label}}</span><strong>{{card.value}}</strong><small>{{card.note}}</small></div>
          <span class="overview-link">查看</span>
        </article>
      </el-tooltip>
    </template>
  </section>
</template>

<style scoped>
.overview-grid { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 20px; }
.overview-card { position: relative; display: flex; min-width: 0; min-height: 132px; align-items: center; gap: 16px; padding: 22px 22px 30px; cursor: pointer; transition: border-color .15s,box-shadow .15s; }
.overview-card:hover { border-color: #bacddd; box-shadow: 0 6px 22px rgba(36,53,72,.07); }
.overview-card:focus-visible { outline: 2px solid #527fa6; outline-offset: 3px; }
.pending-card { height: 100%; }
.overview-icon { display: grid; width: 46px; height: 46px; flex: 0 0 46px; place-items: center; border-radius: 13px; font-size: 22px; }
.tone-blue .overview-icon { background: #eaf2f9; color: #3d6e99; }
.tone-green .overview-icon { background: #eaf5f0; color: #3f7761; }
.tone-amber .overview-icon { background: #faf2e5; color: #926a32; }
.tone-red .overview-icon { background: #fbecea; color: #a94f4b; }
.overview-copy { display: grid; min-width: 0; flex: 1; grid-template-columns: minmax(0,1fr) auto; align-items: center; column-gap: 12px; row-gap: 7px; }
.overview-copy > span { color: #546479; font-size: 15px; font-weight: 600; }
.overview-copy strong { color: #17263a; font-size: 32px; font-weight: 700; letter-spacing: -.035em; font-variant-numeric: tabular-nums; line-height: 1.25; }
.overview-copy small { grid-column: 1/-1; color: #748196; font-size: 13px; line-height: 1.5; overflow-wrap: anywhere; }
.overview-link { position: absolute; right: 20px; bottom: 9px; color: #5f7891; font-size: 12px; opacity: 0; }
.overview-link.always,.overview-card:hover .overview-link,.overview-card:focus-visible .overview-link { opacity: 1; }
.attention-badge { position: absolute; z-index: 2; top: 9px; right: 9px; display: grid; min-width: 25px; height: 25px; place-items: center; padding: 0 6px; border: 2px solid #fff; border-radius: 14px; background: #b94e48; color: #fff; font-size: 12px; font-weight: 700; line-height: 1; }
@media(max-width:1500px) { .overview-grid { grid-template-columns: repeat(2,minmax(0,1fr)); } }
</style>
