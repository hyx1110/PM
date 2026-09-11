<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Calendar, Collection, Timer, TrendCharts, WarningFilled } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import { getDashboardSummary } from '@/api/report'
import type { DashboardSummary } from '@/types/report'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const loading = ref(false)
const data = ref<DashboardSummary>({
  projects_total: 0, projects_running: 0, projects_completed: 0, projects_delayed: 0,
  delayed_tasks: 0, pending_schedules: 0, today_schedules: 0, open_risks: 0,
  critical_risks: 0, today_risks: 0, weekly_planned_hours: 0, monthly_planned_hours: 0,
  weekly_utilization_rate: 0, task_completion_rate: 0, schedule_trend: [],
})
const cards = computed(() => [
  { value: data.value.projects_running, label: '进行中项目', note: `共 ${data.value.projects_total} 个可见项目`, icon: Collection, color: '#315f8e' },
  { value: `${data.value.task_completion_rate}%`, label: '任务完成率', note: `${data.value.delayed_tasks} 个延期任务`, icon: TrendCharts, color: '#4b7b6b' },
  { value: data.value.pending_schedules, label: '待确认排期', note: `今日 ${data.value.today_schedules} 条安排`, icon: Calendar, color: '#92713c' },
  { value: data.value.open_risks, label: '未关闭风险', note: `今日 ${data.value.today_risks} / 严重 ${data.value.critical_risks}`, icon: WarningFilled, color: '#a75858' },
])
const maxHours = computed(() => Math.max(...data.value.schedule_trend.map(item => item.planned_hours), 1))

onMounted(async () => {
  loading.value = true
  try { data.value = await getDashboardSummary() } finally { loading.value = false }
})
</script>

<template>
  <div class="page-shell" v-loading="loading">
    <header class="page-header">
      <div><h1 class="page-title">管理驾驶舱</h1><p class="page-subtitle">{{ userStore.profile?.name }}，这里汇总项目进度、人力排期和实时风险。</p></div>
      <div class="header-actions"><el-button @click="$router.push('/risks')">风险中心</el-button><el-button type="primary" @click="$router.push('/schedules')">共享看板</el-button></div>
    </header>
    <section class="metrics">
      <article v-for="card in cards" :key="card.label" class="surface metric">
        <div class="metric-icon" :style="{ color: card.color, backgroundColor: `${card.color}14` }"><el-icon><component :is="card.icon" /></el-icon></div>
        <div><span>{{ card.label }}</span><strong>{{ card.value }}</strong><small>{{ card.note }}</small></div>
      </article>
    </section>
    <section class="dashboard-grid">
      <article class="surface trend-card">
        <div class="section-title"><div><span class="overline">WORKFORCE TREND</span><h2>近 14 天计划工时</h2></div><div class="week-total"><el-icon><Timer /></el-icon> 本周 {{ data.weekly_planned_hours }}h · 利用率 {{ data.weekly_utilization_rate }}%</div></div>
        <div class="trend-chart">
          <div v-for="item in data.schedule_trend" :key="item.date" class="trend-column" :title="`${item.date}：${item.planned_hours}h`">
            <span class="bar-value">{{ item.planned_hours || '' }}</span>
            <div class="bar" :style="{ height: `${Math.max(item.planned_hours / maxHours * 120, item.planned_hours ? 5 : 1)}px` }"></div>
            <small>{{ dayjs(item.date).format('MM/DD') }}</small>
          </div>
        </div>
      </article>
      <article class="surface health-card">
        <span class="overline">PROJECT HEALTH</span><h2>项目健康概览</h2>
        <div class="health-row"><span>已完成项目</span><strong>{{ data.projects_completed }}</strong></div>
        <div class="health-row danger"><span>延期项目</span><strong>{{ data.projects_delayed }}</strong></div>
        <div class="health-row"><span>进行中项目</span><strong>{{ data.projects_running }}</strong></div>
        <div class="health-row"><span>本月计划工时</span><strong>{{ data.monthly_planned_hours }}h</strong></div>
        <el-progress :percentage="data.task_completion_rate" :stroke-width="8" color="#4b7b6b" />
        <p>任务完成率基于当前可见项目中的全部任务计算。</p>
      </article>
    </section>
  </div>
</template>

<style scoped>
.header-actions{display:flex;gap:10px}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}.metric{display:flex;align-items:center;gap:15px;padding:20px}.metric-icon{display:grid;width:44px;height:44px;place-items:center;border-radius:13px;font-size:20px}.metric span,.metric small{display:block;color:#8993a1;font-size:11px}.metric strong{display:block;margin:3px 0;color:#202b3d;font-size:26px;font-weight:650}.dashboard-grid{display:grid;grid-template-columns:1.7fr 1fr;gap:16px}.trend-card,.health-card{padding:24px}.section-title{display:flex;align-items:start;justify-content:space-between}.overline{color:#7890aa;font-size:10px;font-weight:700;letter-spacing:.16em}.section-title h2,.health-card h2{margin:8px 0 0;color:#26364a;font-size:17px}.week-total{display:flex;align-items:center;gap:6px;border-radius:9px;background:#f3f6f9;padding:8px 11px;color:#64758a;font-size:12px}.trend-chart{display:flex;height:178px;align-items:end;gap:9px;margin-top:18px;border-bottom:1px solid #e9edf1}.trend-column{display:flex;min-width:0;flex:1;flex-direction:column;align-items:center}.bar-value{height:17px;color:#8792a2;font-size:9px}.bar{width:70%;max-width:28px;border-radius:5px 5px 0 0;background:linear-gradient(#6e91b5,#b7cadb)}.trend-column small{padding:8px 0;color:#9aa3af;font-size:9px;white-space:nowrap}.health-card h2{margin-bottom:18px}.health-row{display:flex;justify-content:space-between;border-bottom:1px solid #f0f2f4;padding:12px 0;color:#667386;font-size:13px}.health-row strong{color:#26364a}.health-row.danger strong{color:#b45252}.health-card .el-progress{margin-top:20px}.health-card p{margin:9px 0 0;color:#98a1ad;font-size:11px;line-height:1.6}
</style>
