<script setup lang="ts">
import { computed, ref } from 'vue'
import dayjs from 'dayjs'
import type { DashboardTaskItem } from '@/types/report'

const props = defineProps<{ items: DashboardTaskItem[] }>()
const emit = defineEmits<{ task: [item: DashboardTaskItem] }>()
const expanded = ref(false)
const visibleItems = computed(() => expanded.value ? props.items : props.items.slice(0, 3))
const varianceLabel = (item: DashboardTaskItem) => item.deviation_hours > 0 ? `+${item.deviation_hours}h` : `${item.deviation_hours}h`
const width = (value: number, item: DashboardTaskItem) => `${Math.min(value / Math.max(item.estimated_hours, item.actual_hours, 1) * 100, 100)}%`
</script>

<template>
  <section class="surface compare-card">
    <header class="module-head"><div><h2>计划与实际</h2><p>优先展示延期或工时偏差较大的任务。</p></div><button v-if="items.length>3" class="text-button" :aria-expanded="expanded" @click="expanded=!expanded">{{expanded?'收起':`查看全部 ${items.length} 项`}}</button></header>
    <div v-if="visibleItems.length" class="compare-list">
      <el-tooltip v-for="item in visibleItems" :key="item.id" :content="`${item.project_name} · ${item.owner_name}；计划 ${item.planned_start} 至 ${item.planned_end}；实际 ${item.actual_start || '未开始'} 至 ${item.actual_end || '—'}`" placement="top" :show-after="260">
        <button class="compare-item" @click="emit('task',item)">
          <div class="compare-title"><div><strong>{{item.name}}</strong><small>{{item.project_name}} · {{item.owner_name}}</small></div><span :class="`variance-${item.variance}`">{{varianceLabel(item)}}</span></div>
          <div class="compare-bars"><div><div class="bar-track"><i :style="{width:width(item.estimated_hours,item)}"></i></div><span>预计 {{item.estimated_hours}}h</span></div><div class="actual"><div class="bar-track"><i :class="`variance-${item.variance}`" :style="{width:width(item.actual_hours,item)}"></i></div><span>实际 {{item.actual_hours}}h</span></div></div>
          <div class="compare-periods"><span>计划 {{dayjs(item.planned_start).format('MM/DD')}}–{{dayjs(item.planned_end).format('MM/DD')}}</span><span>实际 {{item.actual_start?dayjs(item.actual_start).format('MM/DD'):'—'}}–{{item.actual_end?dayjs(item.actual_end).format('MM/DD'):'—'}}</span></div>
        </button>
      </el-tooltip>
    </div>
    <div v-else class="compact-empty">暂无任务执行偏差数据</div>
  </section>
</template>

<style scoped>
.compare-card { min-width: 0; padding: 24px; }
.module-head { display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
.module-head h2 { margin: 0; color: #1f2f43; font-size: 20px; font-weight: 650; line-height: 1.5; }
.module-head p { margin: 8px 0 0; color: #6f7f92; font-size: 14px; line-height: 1.6; }
.text-button { border: 0; border-radius: 6px; background: transparent; padding: 8px 0; color: #436d94; font-size: 13px; cursor: pointer; }
.compare-list { display: flex; flex-direction: column; margin-top: 16px; }
.compare-item { width: 100%; border: 0; border-top: 1px solid #e8edf2; background: transparent; padding: 20px 4px; text-align: left; cursor: pointer; }
.compare-item:first-child { border-top: 0; }
.compare-item:last-child { padding-bottom: 4px; }
.compare-item:hover { border-radius: 9px; background: #f6f9fb; }
.compare-title { display: flex; min-width: 0; align-items: flex-start; justify-content: space-between; gap: 14px; }
.compare-title > div { display: flex; min-width: 0; flex-direction: column; gap: 5px; }
.compare-title strong,.compare-title small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.compare-title strong { color: #26384d; font-size: 15px; font-weight: 600; line-height: 1.5; }
.compare-title small { color: #6d7e91; font-size: 13px; line-height: 1.5; }
.compare-title > span { flex: 0 0 auto; border-radius: 7px; padding: 5px 9px; font-size: 13px; font-weight: 600; }
.compare-title .variance-good { background: #eaf5f0; color: #437762; }
.compare-title .variance-warning { background: #faf2e5; color: #936a32; }
.compare-title .variance-severe { background: #fbecea; color: #ac514c; }
.compare-bars { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 14px; }
.bar-track { height: 8px; overflow: hidden; border-radius: 4px; background: #e9edf2; }
.bar-track i { display: block; height: 100%; border-radius: 4px; background: #b7c5d2; }
.actual .bar-track i { background: #527fa6; }
.actual .bar-track .variance-warning { background: #bf9454; }
.actual .bar-track .variance-severe { background: #ba6861; }
.compare-bars span { display: block; margin-top: 7px; color: #52667b; font-size: 13px; line-height: 1.5; }
.compare-periods { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 5px; color: #718095; font-size: 12px; line-height: 1.5; }
.compact-empty { display: grid; min-height: 130px; place-items: center; color: #708095; font-size: 14px; }
button:focus-visible { outline: 2px solid #527fa6; outline-offset: 2px; }
@media(max-width:1440px) { .compare-card { padding: 20px; } }
</style>
