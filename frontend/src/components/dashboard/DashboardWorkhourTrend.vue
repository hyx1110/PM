<script setup lang="ts">
import { computed, ref } from 'vue'
import dayjs from 'dayjs'
import { beijingNow } from '@/utils/time'

interface TrendItem { date: string; planned_hours: number; actual_hours: number }
const props = defineProps<{ items: TrendItem[] }>()
const range = ref<'7' | '14' | 'month'>('14')
const visibleItems = computed(() => {
  if (range.value === '7') return props.items.slice(-7)
  if (range.value === '14') return props.items.slice(-14)
  const month = beijingNow().format('YYYY-MM')
  return props.items.filter(item => item.date.startsWith(month))
})
const maxHours = computed(() => Math.max(...visibleItems.value.flatMap(item => [item.planned_hours, item.actual_hours]), 1))
const height = (value: number) => `${Math.max(value / maxHours.value * 100, value ? 2 : 0)}%`
const plannedTotal = computed(() => Math.round(visibleItems.value.reduce((sum, item) => sum + item.planned_hours, 0) * 10) / 10)
const actualTotal = computed(() => Math.round(visibleItems.value.reduce((sum, item) => sum + item.actual_hours, 0) * 10) / 10)
const deviationTotal = computed(() => Math.round((actualTotal.value - plannedTotal.value) * 10) / 10)
</script>

<template>
  <section class="surface trend-card">
    <header class="module-head"><div><h2>工时趋势</h2><p>计划来自有效预约，实际来自任务执行记录。</p></div><nav class="mini-tabs" aria-label="工时统计范围"><button :class="{active:range==='7'}" :aria-pressed="range==='7'" @click="range='7'">7天</button><button :class="{active:range==='14'}" :aria-pressed="range==='14'" @click="range='14'">14天</button><button :class="{active:range==='month'}" :aria-pressed="range==='month'" @click="range='month'">本月</button></nav></header>
    <div class="trend-meta"><div><small>计划工时</small><strong>{{plannedTotal}}h</strong></div><div><small>实际工时</small><strong>{{actualTotal}}h</strong></div><div class="variance-total" :class="{over:deviationTotal>0}"><small>工时偏差</small><strong>{{deviationTotal>0?'+':''}}{{deviationTotal}}h</strong></div><div class="chart-legend"><span><i class="planned"></i>计划</span><span><i class="actual"></i>实际</span></div></div>
    <div class="chart-scroll" tabindex="0" role="region" aria-label="每日计划工时与实际工时趋势，窄窗口可横向滚动"><div class="trend-chart" :class="{monthly:visibleItems.length>16}">
      <el-tooltip v-for="(item,index) in visibleItems" :key="item.date" :content="`${item.date}：计划 ${item.planned_hours}h，实际 ${item.actual_hours}h，偏差 ${Math.round((item.actual_hours-item.planned_hours)*10)/10}h`" placement="top" :show-after="120">
        <div class="trend-column"><div class="bar-pair"><i class="planned" :style="{height:height(item.planned_hours)}"></i><i class="actual" :class="{over:item.actual_hours>item.planned_hours}" :style="{height:height(item.actual_hours)}"></i></div><small>{{visibleItems.length<=16 || index%5===0 || index===visibleItems.length-1 ? dayjs(item.date).format(visibleItems.length>16?'D':'MM/DD') : ''}}</small></div>
      </el-tooltip>
    </div></div>
  </section>
</template>

<style scoped>
.trend-card { display: flex; min-width: 0; min-height: 0; flex-direction: column; overflow: hidden; padding: 24px; }
.module-head,.trend-meta { flex-shrink: 0; }
.module-head { display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 16px; }
.module-head h2 { margin: 0; color: #1f2f43; font-size: 20px; font-weight: 650; line-height: 1.5; }
.module-head p { margin: 8px 0 0; color: #6f7f92; font-size: 14px; line-height: 1.6; }
.mini-tabs { display: flex; flex-shrink: 0; border: 1px solid #e3eaf1; border-radius: 9px; background: #f4f6f8; padding: 4px; }
.mini-tabs button { min-height: 32px; border: 0; border-radius: 6px; background: transparent; padding: 6px 12px; color: #5d7088; font-size: 13px; cursor: pointer; }
.mini-tabs button.active { background: #fff; color: #2f628f; font-weight: 600; box-shadow: 0 1px 5px rgba(49,76,103,.08); }
.trend-meta { display: flex; align-items: center; flex-wrap: wrap; gap: 18px 32px; margin-top: 22px; border-bottom: 1px solid #edf1f4; padding-bottom: 18px; }
.trend-meta > div:not(.chart-legend) { display: flex; flex-direction: column; gap: 6px; }
.trend-meta small { color: #6e8093; font-size: 13px; }
.trend-meta strong { color: #34465a; font-size: 22px; font-weight: 650; font-variant-numeric: tabular-nums; line-height: 1.3; }
.trend-meta .variance-total strong { color: #477a65; }
.trend-meta .variance-total.over strong { color: #a65b54; }
.chart-legend { display: flex; gap: 16px; margin-left: auto; color: #61758c; font-size: 13px; }
.chart-legend span { display: flex; align-items: center; gap: 7px; }
.chart-legend i { display: block; width: 18px; height: 7px; border-radius: 3px; }
.chart-legend .planned { background: #c0ccd8; }
.chart-legend .actual { background: #527fa6; }
.chart-scroll { min-height: 194px; flex: 1 1 auto; overflow: auto; margin-top: 16px; }
.trend-chart { display: flex; min-width: 620px; min-height: 194px; height: 100%; align-items: flex-end; gap: 4px; border-bottom: 1px solid #dfe6ec; background: repeating-linear-gradient(to bottom,transparent 0,transparent 46px,#eef2f6 47px); }
.trend-column { display: flex; min-width: 0; height: 100%; min-height: 194px; flex: 1; flex-direction: column; align-items: center; }
.bar-pair { display: flex; height: calc(100% - 36px); min-height: 156px; align-items: flex-end; gap: 3px; }
.bar-pair i { display: block; width: 8px; border-radius: 4px 4px 1px 1px; }
.monthly .bar-pair { gap: 2px; }
.monthly .bar-pair i { width: 5px; }
.bar-pair .planned { background: #becbd7; }
.bar-pair .actual { background: #527fa6; }
.bar-pair .actual.over { background: #bd7868; }
.trend-column small { min-height: 36px; padding: 8px 0; color: #62778e; font-size: 12px; line-height: 20px; white-space: nowrap; }
button:focus-visible,.chart-scroll:focus-visible { outline: 2px solid #527fa6; outline-offset: 2px; }
@media(max-width:1440px) { .trend-card { padding: 20px; } }
</style>
