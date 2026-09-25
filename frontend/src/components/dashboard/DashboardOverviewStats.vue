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
.overview-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}.overview-card{position:relative;display:flex;min-width:0;min-height:88px;align-items:center;gap:14px;overflow:hidden;padding:17px 18px 17px 20px;cursor:pointer;transition:border-color .18s ease,box-shadow .18s ease,transform .18s ease}.overview-card::before{position:absolute;top:16px;bottom:16px;left:0;width:3px;border-radius:0 4px 4px 0;background:#6f96bb;content:""}.overview-card:hover,.overview-card:focus-visible{border-color:#ccd8e3;box-shadow:0 13px 34px rgba(36,53,72,.09);outline:0;transform:translateY(-2px)}.pending-card{height:100%;cursor:default}.overview-icon{display:grid;width:42px;height:42px;flex:0 0 42px;place-items:center;border-radius:12px;font-size:19px}.tone-blue .overview-icon{background:#eaf2f9;color:#3d6e99}.tone-green::before{background:#6c9b88}.tone-green .overview-icon{background:#eaf5f0;color:#3f7761}.tone-amber::before{background:#c59a5a}.tone-amber .overview-icon{background:#faf2e5;color:#926a32}.tone-red::before{background:#c97670}.tone-red .overview-icon{background:#fbecea;color:#a94f4b}.overview-copy{display:grid;min-width:0;flex:1;grid-template-columns:minmax(0,1fr) auto;align-items:baseline;column-gap:12px}.overview-copy span{color:#68778a;font-size:12px;font-weight:570}.overview-copy strong{grid-row:1/3;grid-column:2;justify-self:end;color:#17263a;font-size:28px;font-weight:720;letter-spacing:-.04em}.overview-copy small{overflow:hidden;margin-top:6px;color:#8e99a7;font-size:10px;text-overflow:ellipsis;white-space:nowrap}.overview-link{position:absolute;right:18px;bottom:11px;color:#6f8499;font-size:9px;font-weight:600;opacity:0;transition:opacity .18s}.overview-link.always{opacity:.9}.overview-card:hover .overview-link{opacity:1}.attention-badge{position:absolute;z-index:2;top:7px;right:7px;display:grid;min-width:22px;height:22px;place-items:center;border:2px solid #fff;border-radius:11px;background:#c85852;padding:0 5px;color:#fff;font-size:9px;font-weight:750;box-shadow:0 5px 14px rgba(174,78,72,.28)}@media(max-width:1280px){.overview-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
