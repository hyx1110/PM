<script setup lang="ts">
import { computed, ref } from 'vue'
import dayjs from 'dayjs'

interface TrendItem { date: string; planned_hours: number; actual_hours: number }
const props = defineProps<{ items: TrendItem[] }>()
const range = ref<'7' | '14' | 'month'>('14')
const visibleItems = computed(() => {
  if (range.value === '7') return props.items.slice(-7)
  if (range.value === '14') return props.items.slice(-14)
  const month = dayjs().format('YYYY-MM')
  return props.items.filter(item => item.date.startsWith(month))
})
const maxHours = computed(() => Math.max(...visibleItems.value.flatMap(item => [item.planned_hours, item.actual_hours]), 1))
const height = (value: number) => `${Math.max(value / maxHours.value * 112, value ? 3 : 1)}px`
const plannedTotal = computed(() => Math.round(visibleItems.value.reduce((sum, item) => sum + item.planned_hours, 0) * 10) / 10)
const actualTotal = computed(() => Math.round(visibleItems.value.reduce((sum, item) => sum + item.actual_hours, 0) * 10) / 10)
const deviationTotal = computed(() => Math.round((actualTotal.value - plannedTotal.value) * 10) / 10)
</script>

<template>
  <section class="surface trend-card">
    <header class="module-head"><div><span class="eyebrow">WORKHOUR TREND</span><h2>计划工时 vs 实际工时</h2><p>计划来自有效预约，实际来自任务执行记录。</p></div><nav class="mini-tabs"><button :class="{active:range==='7'}" @click="range='7'">7天</button><button :class="{active:range==='14'}" @click="range='14'">14天</button><button :class="{active:range==='month'}" @click="range='month'">本月</button></nav></header>
    <div class="trend-meta"><div><small>计划工时</small><strong>{{plannedTotal}}h</strong></div><div><small>实际工时</small><strong>{{actualTotal}}h</strong></div><div class="variance-total" :class="{over:deviationTotal>0}"><small>工时偏差</small><strong>{{deviationTotal>0?'+':''}}{{deviationTotal}}h</strong></div><div class="chart-legend"><span><i class="planned"></i>计划</span><span><i class="actual"></i>实际</span></div></div>
    <div class="trend-chart">
      <el-tooltip v-for="(item,index) in visibleItems" :key="item.date" :content="`${item.date}：计划 ${item.planned_hours}h，实际 ${item.actual_hours}h，偏差 ${Math.round((item.actual_hours-item.planned_hours)*10)/10}h`" placement="top" :show-after="120">
        <div class="trend-column"><div class="bar-pair"><i class="planned" :style="{height:height(item.planned_hours)}"></i><i class="actual" :class="{over:item.actual_hours>item.planned_hours}" :style="{height:height(item.actual_hours)}"></i></div><small>{{visibleItems.length<=16 || index%5===0 || index===visibleItems.length-1 ? dayjs(item.date).format(visibleItems.length>16?'D':'MM/DD') : ''}}</small></div>
      </el-tooltip>
    </div>
  </section>
</template>

<style scoped>
.trend-card{height:100%;padding:19px 20px}.module-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px}.module-head h2{margin:6px 0 0;color:#1f2f43;font-size:17px;font-weight:680}.module-head p{margin:6px 0 0;color:#8592a2;font-size:10px}.eyebrow{color:#7890a7;font-size:9px;font-weight:780;letter-spacing:.15em}.mini-tabs{display:flex;border:1px solid #e8edf2;border-radius:9px;background:#f4f6f8;padding:3px}.mini-tabs button{border:0;border-radius:6px;background:transparent;padding:5px 9px;color:#718095;font-size:9px;cursor:pointer}.mini-tabs button.active{background:#fff;color:#2f628f;font-weight:650;box-shadow:0 2px 8px rgba(49,76,103,.1)}.trend-meta{display:flex;align-items:center;gap:24px;margin-top:15px;border-bottom:1px solid #edf1f4;padding-bottom:10px}.trend-meta>div:not(.chart-legend){display:flex;flex-direction:column}.trend-meta small{color:#8a96a4;font-size:8px}.trend-meta strong{margin-top:3px;color:#34465a;font-size:13px}.trend-meta .variance-total strong{color:#477a65}.trend-meta .variance-total.over strong{color:#b06058}.chart-legend{display:flex;justify-content:flex-end;gap:12px;margin-left:auto;color:#77869a;font-size:9px}.chart-legend span{display:flex;align-items:center;gap:4px}.chart-legend i{display:block;width:13px;height:5px;border-radius:3px}.chart-legend .planned{background:#c0ccd8}.chart-legend .actual{background:#527fa6}.trend-chart{display:flex;height:142px;align-items:flex-end;gap:5px;margin-top:7px;border-bottom:1px solid #dfe6ec;background:repeating-linear-gradient(to bottom,transparent 0,transparent 35px,#f1f4f7 36px)}.trend-column{display:flex;min-width:0;flex:1;flex-direction:column;align-items:center}.bar-pair{display:flex;height:113px;align-items:flex-end;gap:3px}.bar-pair i{display:block;width:6px;min-width:2px;border-radius:4px 4px 1px 1px}.bar-pair .planned{background:#becbd7}.bar-pair .actual{background:#527fa6}.bar-pair .actual.over{background:#bd7868}.trend-column small{padding:7px 0;color:#8794a3;font-size:8px;white-space:nowrap}
</style>
