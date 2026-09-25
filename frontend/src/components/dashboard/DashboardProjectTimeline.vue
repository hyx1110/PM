<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import dayjs, { type Dayjs } from 'dayjs'
import { ArrowDown, ArrowRight } from '@element-plus/icons-vue'
import type { DashboardProjectTimelineItem, DashboardTaskItem } from '@/types/report'

const props = defineProps<{ projects: DashboardProjectTimelineItem[] }>()
const emit = defineEmits<{ task: [item: DashboardTaskItem]; project: [id: number] }>()
const expanded = ref(new Set<number>())

watch(() => props.projects, (items) => {
  expanded.value = new Set(items.slice(0, 2).map(item => item.id))
}, { immediate: true })

const statusLabel: Record<string, string> = { not_started: '未开始', running: '进行中', completed: '已完成', delayed: '已逾期' }
const allDates = computed(() => [
  dayjs().format('YYYY-MM-DD'),
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
const todayLeft = computed(() => position(dayjs()))

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
function tooltip(item: DashboardTaskItem | DashboardProjectTimelineItem) {
  return `计划：${item.planned_start} 至 ${item.planned_end}\n实际：${item.actual_start || '尚未开始'} 至 ${item.actual_end || '—'}\n进度：${item.progress}%`
}
</script>

<template>
  <section class="surface timeline-card">
    <header class="module-head">
      <div><span class="eyebrow">PROJECT TIMELINE</span><h2>项目进度</h2><p>重点项目的计划与实际执行区间，点击任务查看详情。</p></div>
      <div class="timeline-legend"><span><i class="plan"></i>计划</span><span><i class="actual"></i>实际</span><span><i class="today"></i>今天</span></div>
    </header>
    <div v-if="projects.length" class="timeline-table">
      <div class="timeline-header">
        <div class="name-column">项目 / 任务</div><div class="owner-column">负责人</div>
        <div class="axis-header"><span v-for="tick in ticks" :key="tick.left" :style="{left:`${tick.left}%`}">{{tick.label}}</span></div>
      </div>
      <template v-for="project in projects" :key="project.id">
        <div class="timeline-row project-row">
          <div class="name-column project-name-cell">
            <button class="expand-button" :aria-label="expanded.has(project.id)?'折叠任务':'展开任务'" @click="toggle(project.id)"><el-icon><ArrowDown v-if="expanded.has(project.id)"/><ArrowRight v-else/></el-icon></button>
            <button class="name-button" :title="`${project.code} · ${project.name}`" @click="emit('project',project.id)"><strong>{{project.name}}</strong><small>{{project.completed_task_count}}/{{project.task_count}} 任务 · {{project.progress}}%</small></button>
          </div>
          <div class="owner-column"><span>{{project.manager_name}}</span><small :class="`status-${project.status}`">{{statusLabel[project.status] || project.status}}</small></div>
          <el-tooltip :content="tooltip(project)" placement="top" :show-after="250">
            <div class="axis-cell">
              <i v-for="tick in ticks" :key="tick.left" class="grid-line" :style="{left:`${tick.left}%`}"></i><i class="today-line" :style="{left:`${todayLeft}%`}"></i>
              <span class="range-bar plan-bar" :style="barStyle(project.planned_start,project.planned_end)"></span><span class="range-bar actual-bar" :style="barStyle(project.actual_start,project.actual_end)"></span>
            </div>
          </el-tooltip>
        </div>
        <div v-for="task in expanded.has(project.id)?project.tasks:[]" :key="task.id" class="timeline-row task-row" role="button" tabindex="0" @click="emit('task',task)" @keydown.enter="emit('task',task)">
          <div class="name-column task-name-cell" :title="task.name"><span class="task-guide"></span><strong>{{task.name}}</strong></div>
          <div class="owner-column"><span :title="task.owner_name">{{task.owner_name}}</span><small :class="`status-${task.status}`">{{statusLabel[task.status] || task.status}}</small></div>
          <el-tooltip :content="tooltip(task)" placement="top" :show-after="220">
            <div class="axis-cell">
              <i v-for="tick in ticks" :key="tick.left" class="grid-line" :style="{left:`${tick.left}%`}"></i><i class="today-line" :style="{left:`${todayLeft}%`}"></i>
              <span class="range-bar plan-bar" :style="barStyle(task.planned_start,task.planned_end)"></span><span class="range-bar actual-bar" :class="{overdue:task.status==='delayed'}" :style="barStyle(task.actual_start,task.actual_end)"></span>
            </div>
          </el-tooltip>
        </div>
      </template>
    </div>
    <div v-else class="compact-empty">当前数据范围内暂无已审批项目</div>
  </section>
</template>

<style scoped>
.timeline-card{height:100%;min-width:0;padding:20px}.module-head{display:flex;align-items:flex-start;justify-content:space-between;gap:18px}.eyebrow{color:#7890a7;font-size:9px;font-weight:780;letter-spacing:.15em}.module-head h2{margin:6px 0 0;color:#1f2f43;font-size:17px;font-weight:680}.module-head p{margin:6px 0 0;color:#8592a2;font-size:10px}.timeline-legend{display:flex;align-items:center;gap:14px;border:1px solid #e8edf2;border-radius:9px;background:#fafbfd;padding:6px 8px;color:#718094;font-size:9px}.timeline-legend span{display:flex;align-items:center;gap:5px}.timeline-legend i{display:block;width:17px;height:4px;border-radius:3px}.timeline-legend .plan{background:#ccd6e0}.timeline-legend .actual{background:#4f7fa8}.timeline-legend .today{width:2px;height:13px;background:#c36761}.timeline-table{overflow:hidden;margin-top:16px;border:1px solid #e3e9ef;border-radius:11px}.timeline-header,.timeline-row{display:grid;grid-template-columns:minmax(190px,1.1fr) 112px minmax(300px,2fr);align-items:stretch}.timeline-header{height:35px;background:#f6f8fa;color:#78879a;font-size:9px;font-weight:620}.timeline-header>div{display:flex;align-items:center;padding:0 11px}.axis-header{position:relative;padding:0!important}.axis-header span{position:absolute;transform:translateX(-50%);white-space:nowrap}.axis-header span:first-child{transform:none}.axis-header span:last-child{transform:translateX(-100%)}.timeline-row{min-height:47px;border-top:1px solid #e8edf2}.project-row{background:#fbfcfd}.task-row{min-height:41px;background:#fff;cursor:pointer;transition:background .15s}.task-row:hover{background:#f5f8fb}.name-column,.owner-column{min-width:0;border-right:1px solid #e8edf2;padding:8px 11px}.project-name-cell{display:flex;align-items:center;gap:7px;border-left:3px solid #7396b6;padding-left:8px}.expand-button{display:grid;width:24px;height:24px;flex:0 0 24px;place-items:center;border:0;border-radius:7px;background:#eef3f7;color:#647b92;cursor:pointer}.expand-button:hover{background:#e2ebf3;color:#2f628f}.name-button{display:flex;min-width:0;flex-direction:column;border:0;background:transparent;padding:0;text-align:left;cursor:pointer}.name-button strong,.task-name-cell strong{overflow:hidden;color:#26384d;font-size:11px;text-overflow:ellipsis;white-space:nowrap}.name-button strong{font-weight:680}.name-button small{margin-top:4px;color:#8996a5;font-size:9px}.owner-column{display:flex;min-width:0;flex-direction:column;justify-content:center}.owner-column span{overflow:hidden;color:#536479;font-size:10px;font-weight:560;text-overflow:ellipsis;white-space:nowrap}.owner-column small{width:max-content;margin-top:4px;border-radius:5px;background:#f1f4f7;padding:2px 5px;font-size:8px}.owner-column .status-delayed{background:#fbeeed;color:#ad5651}.owner-column .status-running{background:#eaf2f8;color:#47749c}.owner-column .status-completed{background:#eaf5f0;color:#467865}.owner-column .status-not_started{background:#f1f3f5;color:#7c8896}.task-name-cell{display:flex;align-items:center;gap:8px;padding-left:40px}.task-guide{width:9px;height:1px;flex:0 0 9px;background:#bfcbd7}.task-name-cell strong{font-weight:540}.axis-cell{position:relative;min-width:0;overflow:hidden;background:linear-gradient(to bottom,rgba(247,249,251,.45),rgba(255,255,255,0))}.grid-line{position:absolute;top:0;bottom:0;width:1px;background:#e9eef3}.today-line{position:absolute;z-index:2;top:0;bottom:0;width:2px;background:#c36761;opacity:.8}.range-bar{position:absolute;min-width:4px;border-radius:5px}.plan-bar{top:11px;height:6px;background:#ccd6e0}.actual-bar{top:24px;height:8px;background:#4f7fa8;box-shadow:0 2px 5px rgba(67,112,151,.14)}.actual-bar.overdue{background:#bc6a63}.task-row .plan-bar{top:9px}.task-row .actual-bar{top:22px}.compact-empty{display:grid;height:190px;place-items:center;color:#8d99a7;font-size:11px}
</style>
