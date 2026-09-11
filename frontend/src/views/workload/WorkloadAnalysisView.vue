<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import type { TagProps } from 'element-plus'
import { getWorkloadSummary } from '@/api/report'
import type { WorkloadSummary } from '@/types/report'

const loading = ref(false)
const form = reactive({ range: [dayjs().startOf('month').format('YYYY-MM-DD'), dayjs().endOf('month').format('YYYY-MM-DD')], granularity: 'week' })
const data = ref<WorkloadSummary>({ range: { start_date: '', end_date: '', granularity: 'week' }, periods: [], users: [], projects: [] })
const maxPeriod = computed(() => Math.max(...data.value.periods.map(item => item.planned_hours), 1))
const counts = computed(() => ({ overloaded: data.value.users.filter(item => item.load_status === 'overloaded').length, idle: data.value.users.filter(item => item.load_status === 'idle').length, normal: data.value.users.filter(item => item.load_status === 'normal').length }))
const statusLabel: Record<string,string> = { overloaded: '超负载', idle: '空闲', normal: '正常' }
const statusType: Record<string,TagProps['type']> = { overloaded: 'danger', idle: 'info', normal: 'success' }
async function load() { loading.value = true; try { data.value = await getWorkloadSummary({ start_date: form.range[0], end_date: form.range[1], granularity: form.granularity }) } finally { loading.value = false } }
onMounted(load)
</script>

<template>
  <div class="page-shell" v-loading="loading">
    <header class="page-header"><div><h1 class="page-title">人员负载分析</h1><p class="page-subtitle">按日、周、月查看计划工时、人员利用率、项目投入占比和空闲/超负载状态。</p></div></header>
    <section class="surface filter-bar"><el-date-picker v-model="form.range" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始" end-placeholder="结束"/><el-segmented v-model="form.granularity" :options="[{label:'日',value:'day'},{label:'周',value:'week'},{label:'月',value:'month'}]"/><el-button type="primary" @click="load">分析</el-button></section>
    <section class="summary"><article class="surface"><span>统计人员</span><strong>{{ data.users.length }}</strong></article><article class="surface danger"><span>超负载</span><strong>{{ counts.overloaded }}</strong></article><article class="surface idle"><span>空闲</span><strong>{{ counts.idle }}</strong></article><article class="surface normal"><span>负载正常</span><strong>{{ counts.normal }}</strong></article></section>
    <section class="analysis-grid">
      <article class="surface chart-card"><h2>周期计划工时</h2><div class="bars"><div v-for="item in data.periods" :key="item.period" class="bar-row"><span>{{item.period}}</span><div class="track"><i :style="{width:`${item.planned_hours/maxPeriod*100}%`}"></i></div><strong>{{item.planned_hours}}h</strong></div><el-empty v-if="!data.periods.length" description="当前周期暂无已确认排期"/></div></article>
      <article class="surface chart-card"><h2>项目投入占比</h2><div class="shares"><div v-for="item in data.projects.slice(0,10)" :key="item.project_id"><div><span>{{item.project_name}}</span><strong>{{item.share}}%</strong></div><el-progress :percentage="item.share" :show-text="false" :stroke-width="7" color="#7795b3"/><small>{{item.planned_hours}}h</small></div><el-empty v-if="!data.projects.length" description="暂无项目投入数据"/></div></article>
    </section>
    <section class="surface table-card"><el-table :data="data.users"><el-table-column type="index" width="55"/><el-table-column prop="user_name" label="人员" min-width="150"/><el-table-column prop="planned_hours" label="计划工时" width="120"/><el-table-column prop="available_hours" label="可用工时" width="120"/><el-table-column label="利用率" min-width="260"><template #default="{row}"><div class="load-cell"><el-progress :percentage="Math.min(row.load_rate,100)" :show-text="false" :stroke-width="8" :color="row.load_status==='overloaded'?'#b95b5b':row.load_status==='idle'?'#96a5b5':'#4f8b6f'"/><strong>{{row.load_rate}}%</strong></div></template></el-table-column><el-table-column label="负载状态" width="110"><template #default="{row}"><el-tag :type="statusType[row.load_status]">{{statusLabel[row.load_status]}}</el-tag></template></el-table-column></el-table></section>
  </div>
</template>

<style scoped>
.summary{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}.summary article{padding:19px 22px;border-left:3px solid #6688a9}.summary span{display:block;color:#8994a3;font-size:11px}.summary strong{display:block;margin-top:5px;color:#27364a;font-size:25px}.summary .danger{border-left-color:#b75959}.summary .idle{border-left-color:#9aa8b6}.summary .normal{border-left-color:#4f8b6f}.analysis-grid{display:grid;grid-template-columns:1.3fr 1fr;gap:16px}.chart-card{min-height:300px;padding:22px}.chart-card h2{margin:0 0 18px;color:#344156;font-size:15px}.bars{display:flex;max-height:300px;flex-direction:column;gap:12px;overflow:auto}.bar-row{display:grid;grid-template-columns:90px 1fr 60px;align-items:center;gap:10px;color:#7b8797;font-size:11px}.bar-row strong{text-align:right;color:#536175}.track{height:9px;overflow:hidden;border-radius:8px;background:#eef1f4}.track i{display:block;height:100%;border-radius:8px;background:linear-gradient(90deg,#6e90b2,#acc2d5)}.shares{display:flex;flex-direction:column;gap:13px}.shares>div{display:grid;grid-template-columns:1fr 45px;column-gap:10px}.shares>div>div{grid-column:1/3;display:flex;justify-content:space-between;margin-bottom:5px;color:#697689;font-size:11px}.shares small{color:#98a1ae;font-size:10px;text-align:right}.load-cell{display:grid;grid-template-columns:1fr 55px;align-items:center;gap:12px}.load-cell strong{color:#667487;font-size:11px}
</style>
