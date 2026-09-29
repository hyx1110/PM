<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import dayjs, { type Dayjs } from 'dayjs'
import { ArrowDown, ArrowRight } from '@element-plus/icons-vue'
import type { DashboardProjectTimelineItem, DashboardTaskItem } from '@/types/report'
import { beijingNow } from '@/utils/time'

const props = defineProps<{ projects: DashboardProjectTimelineItem[] }>()
const emit = defineEmits<{ task: [item: DashboardTaskItem]; project: [id: number] }>()
const expanded = ref(new Set<number>())
const expandableProjects = computed(() => props.projects.filter(project => project.tasks.length > 0))
const allExpanded = computed(() => expandableProjects.value.length > 0 && expandableProjects.value.every(project => expanded.value.has(project.id)))

watch(() => props.projects, (items) => {
  // Start with project summaries. Refreshes preserve explicit expand/collapse
  // choices and only discard projects that no longer exist in this scope.
  const availableIds = new Set(items.filter(item => item.tasks.length).map(item => item.id))
  expanded.value = new Set([...expanded.value].filter(id => availableIds.has(id)))
}, { immediate: true })

const statusLabel: Record<string, string> = { not_started: '未开始', running: '进行中', completed: '已完成', delayed: '已逾期' }
const allDates = computed(() => [
  beijingNow().format('YYYY-MM-DD'),
  ...(props.projects.flatMap(project => [
    project.planned_start, project.planned_end, project.actual_start, project.actual_end,
    ...project.tasks.flatMap(task => [task.planned_start, task.planned_end, task.actual_start, task.actual_end]),
  ]).filter(Boolean) as string[]),
])
const rangeStart = computed(() => {
  if (!allDates.value.length) return dayjs().subtract(7, 'day')
  return allDates.value.reduce((min, value) => dayjs(value).isBefore(min) ? dayjs(value) : min, dayjs(allDates.value[0])).subtract(1, 'day')
})
const rangeEnd = computed(() => {
  if (!allDates.value.length) return dayjs().add(7, 'day')
  return allDates.value.reduce((max, value) => dayjs(value).isAfter(max) ? dayjs(value) : max, dayjs(allDates.value[0])).add(1, 'day')
})
const totalDays = computed(() => Math.max(rangeEnd.value.diff(rangeStart.value, 'day') + 1, 1))
const ticks = computed(() => Array.from({ length: 5 }, (_, index) => {
  const ratio = index / 4
  return { left: ratio * 100, label: rangeStart.value.add(Math.round((totalDays.value - 1) * ratio), 'day').format('MM/DD') }
}))
const todayLeft = computed(() => position(beijingNow().format('YYYY-MM-DD')))

function position(value: string | Dayjs) {
  const ratio = dayjs(value).startOf('day').diff(rangeStart.value.startOf('day'), 'day') / totalDays.value * 100
  return Math.max(0, Math.min(ratio, 100))
}
function barStyle(start?: string | null, end?: string | null) {
  if (!start) return { display: 'none' }
  const left = position(start)
  const right = position(end || start)
  return { left: `${left}%`, width: `${Math.max(right - left, 1.1)}%` }
}
function toggle(id: number) {
  const next = new Set(expanded.value)
  next.has(id) ? next.delete(id) : next.add(id)
  expanded.value = next
}
function toggleAll() {
  expanded.value = allExpanded.value ? new Set() : new Set(expandableProjects.value.map(project => project.id))
}
function tooltip(item: DashboardTaskItem | DashboardProjectTimelineItem) {
  return `计划：${item.planned_start} 至 ${item.planned_end}\n实际：${item.actual_start || '尚未开始'} 至 ${item.actual_end || '—'}\n进度：${item.progress}%`
}
</script>

<template>
  <section class="surface timeline-card">
    <header class="module-head">
      <div><h2>项目进度 <span class="project-count">{{projects.length}} 个项目</span></h2><p>展示本人及下属相关的已审批项目；展开查看重点任务，点击任务可查看详情。</p></div>
      <div class="timeline-tools">
        <div class="timeline-legend"><span><i class="plan"></i>计划</span><span><i class="actual"></i>实际</span><span><i class="today"></i>今天</span></div>
        <button v-if="expandableProjects.length" class="expand-all" :aria-label="allExpanded?'收起全部项目的重点任务':'展开全部项目的重点任务'" @click="toggleAll">{{allExpanded?'全部收起':'全部展开'}}</button>
      </div>
    </header>
    <div v-if="projects.length" class="timeline-scroll" tabindex="0" role="region" aria-label="项目甘特图，可上下滚动查看全部项目，窄窗口可横向滚动">
    <div class="timeline-table">
      <div class="timeline-header">
        <div class="name-column">项目 / 重点任务</div><div class="owner-column">负责人 / 状态</div>
        <div class="axis-header"><small class="axis-range">{{rangeStart.format('YYYY.MM.DD')}} — {{rangeEnd.format('YYYY.MM.DD')}}</small><span v-for="tick in ticks" :key="tick.left" :style="{left:`${tick.left}%`}">{{tick.label}}</span></div>
      </div>
      <template v-for="project in projects" :key="project.id">
        <div class="timeline-row project-row">
          <div class="name-column project-name-cell">
            <button class="expand-button" :disabled="!project.tasks.length" :aria-expanded="expanded.has(project.id)" :aria-controls="`dashboard-project-tasks-${project.id}`" :aria-label="`${expanded.has(project.id)?'折叠':'展开'} ${project.name} 的任务`" @click="toggle(project.id)"><el-icon><ArrowDown v-if="expanded.has(project.id)"/><ArrowRight v-else/></el-icon></button>
            <button class="name-button" :title="`${project.code} · ${project.name}`" @click="emit('project',project.id)"><strong>{{project.name}}</strong><small>{{project.completed_task_count}}/{{project.task_count}} 任务 · {{project.progress}}%</small></button>
          </div>
          <div class="owner-column"><span :title="project.manager_name">{{project.manager_name}}</span><small :class="`status-${project.status}`">{{statusLabel[project.status] || project.status}}</small></div>
          <el-tooltip :content="tooltip(project)" popper-class="dashboard-timeline-tooltip" placement="top" :show-after="250">
            <div class="axis-cell">
              <i v-for="tick in ticks" :key="tick.left" class="grid-line" :style="{left:`${tick.left}%`}"></i><i class="today-line" :style="{left:`${todayLeft}%`}"></i>
              <span class="range-bar plan-bar" :style="barStyle(project.planned_start,project.planned_end)"></span><span class="range-bar actual-bar" :style="barStyle(project.actual_start,project.actual_end)"></span>
            </div>
          </el-tooltip>
        </div>
        <div v-if="expanded.has(project.id)" :id="`dashboard-project-tasks-${project.id}`">
        <div v-for="task in project.tasks" :key="task.id" class="timeline-row task-row" role="button" tabindex="0" @click="emit('task',task)" @keydown.enter="emit('task',task)" @keydown.space.prevent="emit('task',task)">
          <div class="name-column task-name-cell" :title="task.name"><span class="task-guide"></span><strong>{{task.name}}</strong></div>
          <div class="owner-column"><span :title="task.owner_name">{{task.owner_name}}</span><small :class="`status-${task.status}`">{{statusLabel[task.status] || task.status}}</small></div>
          <el-tooltip :content="tooltip(task)" popper-class="dashboard-timeline-tooltip" placement="top" :show-after="220">
            <div class="axis-cell">
              <i v-for="tick in ticks" :key="tick.left" class="grid-line" :style="{left:`${tick.left}%`}"></i><i class="today-line" :style="{left:`${todayLeft}%`}"></i>
              <span class="range-bar plan-bar" :style="barStyle(task.planned_start,task.planned_end)"></span><span class="range-bar actual-bar" :class="{overdue:task.status==='delayed'}" :style="barStyle(task.actual_start,task.actual_end)"></span>
            </div>
          </el-tooltip>
        </div>
        <div v-if="project.tasks.length" class="project-tasks-footer"><span>首页展示 {{project.tasks.length}} 条重点任务</span><button @click="emit('project',project.id)">查看项目全部任务 →</button></div>
        </div>
      </template>
    </div>
    </div>
    <div v-else class="compact-empty">本人及下属暂无相关的已审批项目</div>
  </section>
</template>

<style scoped>
.timeline-card { display: flex; min-width: 0; min-height: 0; flex-direction: column; overflow: hidden; padding: 24px; }
.module-head { flex-shrink: 0; }
.module-head { display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 16px 24px; }
.module-head h2 { margin: 0; color: #1f2f43; font-size: 20px; font-weight: 650; line-height: 1.5; }
.project-count { margin-left: 10px; color: #6f7f92; font-size: 13px; font-weight: 500; white-space: nowrap; }
.module-head p { margin: 8px 0 0; color: #6f7f92; font-size: 14px; line-height: 1.6; }
.timeline-tools { display: flex; align-items: center; flex-wrap: wrap; gap: 20px; }
.timeline-legend { display: flex; align-items: center; gap: 18px; color: #5c6d81; font-size: 13px; }
.timeline-legend span { display: flex; align-items: center; gap: 7px; }
.timeline-legend i { display: block; width: 22px; height: 7px; border-radius: 3px; }
.timeline-legend .plan { background: #c4d0dc; }
.timeline-legend .actual { background: #4f7fa8; }
.timeline-legend .today { width: 2px; height: 17px; background: #c36761; }
.expand-all { min-height: 36px; border: 1px solid #dce5ee; border-radius: 8px; background: #f8fafc; padding: 7px 12px; color: #3e6284; font-size: 13px; cursor: pointer; }
.expand-all:hover { background: #edf3f8; }
.timeline-scroll { min-height: 0; flex: 1 1 auto; overflow: auto; margin-top: 22px; border: 1px solid #e1e7ed; border-radius: 12px; overscroll-behavior: contain; }
.timeline-table { min-width: 940px; }
.timeline-header,.timeline-row { display: grid; grid-template-columns: 280px 160px minmax(500px,1fr); align-items: stretch; }
.timeline-header { position: sticky; top: 0; z-index: 5; min-height: 64px; background: #f5f7fa; color: #5c6d81; font-size: 13px; font-weight: 600; }
.timeline-header > div { display: flex; align-items: center; padding: 0 16px; }
.axis-header { position: relative; padding: 0 12px!important; }
.axis-header .axis-range { position: absolute; top: 8px; left: 14px; color: #697d91; font-size: 12px; font-weight: 500; }
.axis-header > span { position: absolute; bottom: 9px; transform: translateX(-50%); white-space: nowrap; }
.axis-header > span:first-of-type { transform: none; padding-left: 8px; }
.axis-header > span:last-of-type { transform: translateX(-100%); padding-right: 8px; }
.timeline-row { min-height: 80px; border-top: 1px solid #e6ecf2; }
.project-row { background: #f7f9fc; }
.task-row { min-height: 68px; background: #fff; cursor: pointer; }
.task-row:hover { background: #f2f7fb; }
.name-column,.owner-column { position: sticky; min-width: 0; z-index: 3; border-right: 1px solid #e3eaf1; padding: 12px 16px; background: inherit; }
.name-column { left: 0; }
.owner-column { left: 280px; }
.project-name-cell { display: flex; align-items: center; gap: 12px; border-left: 3px solid #7396b6; padding-left: 12px; }
.expand-button { display: grid; width: 32px; height: 32px; flex: 0 0 32px; place-items: center; border: 0; border-radius: 8px; background: #e9f0f6; color: #486783; font-size: 16px; cursor: pointer; }
.expand-button:hover:not(:disabled) { background: #dce8f2; }
.expand-button:disabled { opacity: .4; cursor: default; }
.name-button { display: flex; min-width: 0; flex-direction: column; gap: 5px; border: 0; background: transparent; padding: 0; text-align: left; cursor: pointer; }
.name-button strong,.task-name-cell strong { overflow: hidden; color: #26384d; font-size: 15px; text-overflow: ellipsis; white-space: nowrap; line-height: 1.5; }
.name-button strong { max-width: 100%; font-weight: 650; }
.name-button small { color: #687c90; font-size: 13px; line-height: 1.5; }
.owner-column { display: flex; flex-direction: column; justify-content: center; gap: 5px; }
.owner-column > span { overflow: hidden; color: #465a70; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.owner-column small { width: max-content; border-radius: 5px; padding: 2px 7px; font-size: 12px; line-height: 1.5; }
.status-delayed { background: #fbeeed; color: #a44f49; }
.status-running { background: #eaf2f8; color: #3e6990; }
.status-completed { background: #eaf5f0; color: #3e725d; }
.status-not_started { background: #edf0f3; color: #5f6f80; }
.task-name-cell { display: flex; align-items: center; gap: 10px; padding-left: 50px; }
.task-guide { width: 10px; height: 1px; flex: 0 0 10px; background: #acbece; }
.task-name-cell strong { font-weight: 500; }
.axis-cell { position: relative; min-width: 0; overflow: hidden; }
.grid-line { position: absolute; top: 0; bottom: 0; width: 1px; background: #e6ecf2; }
.today-line { position: absolute; z-index: 2; top: 0; bottom: 0; width: 2px; background: #c36761; opacity: .8; }
.range-bar { position: absolute; min-width: 4px; border-radius: 4px; }
.plan-bar { top: 22px; height: 8px; background: #c4d0dc; }
.actual-bar { top: 42px; height: 10px; background: #4f7fa8; }
.actual-bar.overdue { background: #bc6a63; }
.task-row .plan-bar { top: 16px; }
.task-row .actual-bar { top: 36px; }
.project-tasks-footer { display: flex; justify-content: space-between; align-items: center; gap: 16px; border-top: 1px solid #edf1f5; background: #fff; padding: 10px 18px 10px 54px; color: #768599; font-size: 12px; }
.project-tasks-footer button { border: 0; background: transparent; padding: 5px 0; color: #436d94; font-size: 13px; cursor: pointer; }
.compact-empty { display: grid; min-height: 150px; place-items: center; color: #708095; font-size: 14px; }
button:focus-visible,.task-row:focus-visible,.timeline-scroll:focus-visible { outline: 2px solid #527fa6; outline-offset: -2px; }
@media(max-width:1440px) { .timeline-card { padding: 20px; } }
</style>

<style>
.dashboard-timeline-tooltip { white-space: pre-line; max-width: 420px; font-size: 14px; line-height: 1.7; }
</style>
