<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import { getAnalyticsReport } from '@/api/report'
import type { AnalyticsReport } from '@/types/report'

const loading = ref(false)
const form = reactive({ range: [dayjs().subtract(2,'month').startOf('month').format('YYYY-MM-DD'), dayjs().format('YYYY-MM-DD')] })
const data = ref<AnalyticsReport>({ range: { start_date: '', end_date: '' }, overview: { project_count: 0, task_count: 0, task_completion_rate: 0, planned_hours: 0, actual_hours: 0, plan_actual_rate: 0, project_delay_rate: 0 }, trend: [], projects: [], members: [], workforce_share: [] })
const maxTrend = computed(() => Math.max(...data.value.trend.flatMap(item => [item.planned_hours,item.actual_hours]),1))
async function load() { loading.value = true; try { data.value = await getAnalyticsReport({ start_date: form.range[0], end_date: form.range[1] }) } finally { loading.value = false } }
onMounted(load)
</script>

<template>
  <div class="page-shell" v-loading="loading">
    <header class="page-header"><div><h1 class="page-title">经营分析报表</h1><p class="page-subtitle">对比计划与实际、项目延期率、成员达成、项目人力占比和资源利用情况。</p></div></header>
    <section class="surface filter-bar"><el-date-picker v-model="form.range" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始" end-placeholder="结束"/><el-button type="primary" @click="load">生成报表</el-button></section>
    <section class="overview"><article class="surface"><span>计划工时</span><strong>{{data.overview.planned_hours}}h</strong></article><article class="surface"><span>实际工时</span><strong>{{data.overview.actual_hours}}h</strong></article><article class="surface"><span>计划兑现率</span><strong>{{data.overview.plan_actual_rate}}%</strong></article><article class="surface"><span>任务完成率</span><strong>{{data.overview.task_completion_rate}}%</strong></article><article class="surface danger"><span>项目延期率</span><strong>{{data.overview.project_delay_rate}}%</strong></article></section>
    <section class="surface trend-card"><div class="section-head"><h2>计划 / 实际工时趋势</h2><div class="legend"><span class="planned">计划</span><span class="actual">实际</span></div></div><div class="trend"><div v-for="item in data.trend" :key="item.date" class="day" :title="`${item.date} 计划 ${item.planned_hours}h / 实际 ${item.actual_hours}h`"><div class="columns"><i class="planned" :style="{height:`${Math.max(item.planned_hours/maxTrend*130,item.planned_hours?3:0)}px`}"></i><i class="actual" :style="{height:`${Math.max(item.actual_hours/maxTrend*130,item.actual_hours?3:0)}px`}"></i></div><small>{{dayjs(item.date).format('MM/DD')}}</small></div></div></section>
    <section class="surface report-tabs"><el-tabs>
      <el-tab-pane label="项目分析"><el-table :data="data.projects"><el-table-column prop="project_name" label="项目" min-width="180"/><el-table-column prop="planned_hours" label="计划工时" width="120"/><el-table-column prop="actual_hours" label="实际工时" width="120"/><el-table-column label="任务完成率" min-width="200"><template #default="{row}"><el-progress :percentage="row.task_completion_rate" :stroke-width="7"/></template></el-table-column><el-table-column label="延期" width="90"><template #default="{row}"><el-tag :type="row.delayed?'danger':'success'">{{row.delayed?'是':'否'}}</el-tag></template></el-table-column></el-table></el-tab-pane>
      <el-tab-pane label="成员达成"><el-table :data="data.members"><el-table-column prop="user_name" label="成员" min-width="140"/><el-table-column prop="task_count" label="任务数" width="100"/><el-table-column prop="completed_tasks" label="已完成" width="100"/><el-table-column prop="actual_hours" label="实际工时" width="120"/><el-table-column label="平均达成率" min-width="200"><template #default="{row}"><el-progress :percentage="row.task_achievement_rate" :stroke-width="7" color="#4f8b6f"/></template></el-table-column></el-table></el-tab-pane>
      <el-tab-pane label="项目人力占比"><el-table :data="data.workforce_share"><el-table-column prop="project_name" label="项目" min-width="180"/><el-table-column prop="user_name" label="人员" width="130"/><el-table-column prop="actual_hours" label="实际工时" width="120"/><el-table-column label="项目内占比" min-width="220"><template #default="{row}"><div class="share-cell"><el-progress :percentage="row.share" :show-text="false" :stroke-width="8"/><span>{{row.share}}%</span></div></template></el-table-column></el-table></el-tab-pane>
    </el-tabs></section>
  </div>
</template>

<style scoped>
.overview{display:grid;grid-template-columns:repeat(5,1fr);gap:14px}.overview article{padding:18px 20px;border-top:3px solid #6d8dac}.overview span{display:block;color:#8994a2;font-size:11px}.overview strong{display:block;margin-top:6px;color:#27364a;font-size:23px}.overview .danger{border-top-color:#b85858}.trend-card{padding:22px}.section-head{display:flex;align-items:center;justify-content:space-between}.section-head h2{margin:0;color:#344156;font-size:15px}.legend{display:flex;gap:16px;color:#788495;font-size:11px}.legend span:before{display:inline-block;width:8px;height:8px;margin-right:5px;border-radius:2px;background:#83a1bd;content:''}.legend .actual:before{background:#78a18e}.trend{display:flex;height:180px;align-items:end;gap:4px;margin-top:20px;border-bottom:1px solid #e8ecf0;overflow-x:auto}.day{display:flex;min-width:22px;flex:1;flex-direction:column;align-items:center}.columns{display:flex;height:135px;align-items:end;gap:2px}.columns i{display:block;width:6px;border-radius:3px 3px 0 0;background:#83a1bd}.columns i.actual{background:#78a18e}.day small{padding:7px 0;color:#9aa4b0;font-size:8px}.report-tabs{padding:10px 20px 20px}.share-cell{display:grid;grid-template-columns:1fr 55px;align-items:center;gap:10px}.share-cell span{color:#718095;font-size:11px}
</style>
