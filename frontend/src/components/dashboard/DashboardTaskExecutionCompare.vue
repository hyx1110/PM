<script setup lang="ts">
import { computed } from 'vue'
import dayjs from 'dayjs'
import type { DashboardTaskItem } from '@/types/report'

const props = defineProps<{ items: DashboardTaskItem[] }>()
const emit = defineEmits<{ task: [item: DashboardTaskItem] }>()
const visibleItems = computed(() => props.items.slice(0, 5))
const varianceLabel = (item: DashboardTaskItem) => item.deviation_hours > 0 ? `+${item.deviation_hours}h` : `${item.deviation_hours}h`
const width = (value: number, item: DashboardTaskItem) => `${Math.min(value / Math.max(item.estimated_hours, item.actual_hours, 1) * 100, 100)}%`
</script>

<template>
  <section class="surface compare-card">
    <header class="module-head"><div><span class="eyebrow">TIME VARIANCE</span><h2>计划与实际</h2><p>优先展示延期或工时偏差较大的任务。</p></div></header>
    <div v-if="visibleItems.length" class="compare-list">
      <el-tooltip v-for="item in visibleItems" :key="item.id" :content="`${item.project_name} · ${item.owner_name}；计划 ${item.planned_start} 至 ${item.planned_end}；实际 ${item.actual_start || '未开始'} 至 ${item.actual_end || '—'}`" placement="left" :show-after="260">
        <button class="compare-item" @click="emit('task',item)">
          <div class="compare-title"><div><strong>{{item.name}}</strong><small>{{item.project_name}} · {{item.owner_name}}</small></div><span :class="`variance-${item.variance}`">{{varianceLabel(item)}}</span></div>
          <div class="compare-bars"><div><i :style="{width:width(item.estimated_hours,item)}"></i><span>预计 {{item.estimated_hours}}h</span></div><div class="actual"><i :class="`variance-${item.variance}`" :style="{width:width(item.actual_hours,item)}"></i><span>实际 {{item.actual_hours}}h</span></div></div>
          <div class="compare-periods"><span>计划 {{dayjs(item.planned_start).format('MM/DD')}}–{{dayjs(item.planned_end).format('MM/DD')}}</span><span>实际 {{item.actual_start?dayjs(item.actual_start).format('MM/DD'):'—'}}–{{item.actual_end?dayjs(item.actual_end).format('MM/DD'):'—'}}</span></div>
        </button>
      </el-tooltip>
    </div>
    <div v-else class="compact-empty">暂无任务执行偏差数据</div>
  </section>
</template>

<style scoped>
.compare-card{height:100%;padding:20px}.module-head h2{margin:6px 0 0;color:#1f2f43;font-size:17px;font-weight:680}.module-head p{margin:6px 0 0;color:#8592a2;font-size:10px}.eyebrow{color:#7890a7;font-size:9px;font-weight:780;letter-spacing:.15em}.compare-list{display:flex;flex-direction:column;margin-top:14px}.compare-item{width:100%;border:0;border-top:1px solid #e8edf2;background:transparent;padding:12px 3px;text-align:left;cursor:pointer;transition:background .15s,padding .15s}.compare-item:first-child{border-top:0}.compare-item:hover{border-radius:9px;background:#f6f9fb;padding-right:8px;padding-left:8px}.compare-title{display:flex;min-width:0;align-items:flex-start;justify-content:space-between;gap:10px}.compare-title>div{display:flex;min-width:0;flex-direction:column}.compare-title strong,.compare-title small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.compare-title strong{color:#26384d;font-size:11px;font-weight:660}.compare-title small{margin-top:4px;color:#7f8d9e;font-size:9px}.compare-title>span{flex:0 0 auto;border-radius:7px;padding:4px 7px;font-size:9px;font-weight:700}.variance-good{background:#eaf5f0!important;color:#437762!important}.variance-warning{background:#faf2e5!important;color:#936a32!important}.variance-severe{background:#fbecea!important;color:#ac514c!important}.compare-bars{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}.compare-bars>div{position:relative;height:6px;border-radius:4px;background:#e9edf1}.compare-bars i{display:block;height:100%;border-radius:4px;background:#b7c5d2}.compare-bars .actual i{background:#527fa6}.compare-bars span{display:block;margin-top:5px;color:#8b97a5;font-size:8px}.compare-periods{display:flex;justify-content:space-between;margin-top:13px;color:#8794a3;font-size:8px}.compact-empty{display:grid;height:200px;place-items:center;color:#8d99a7;font-size:11px}
</style>
