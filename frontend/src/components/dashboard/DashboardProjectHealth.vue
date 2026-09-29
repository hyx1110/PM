<script setup lang="ts">
import { computed } from 'vue'
import type { DashboardProjectHealth } from '@/types/report'

const props = defineProps<{ items: DashboardProjectHealth[] }>()
const emit = defineEmits<{ project: [id: number] }>()
const labels = { normal: '正常', attention: '关注', risk: '风险', delayed: '延期' }
const summary = computed(() => ({
  normal: props.items.filter(item => item.status === 'normal').length,
  attention: props.items.filter(item => item.status === 'attention').length,
  risk: props.items.filter(item => item.status === 'risk' || item.status === 'delayed').length,
}))
</script>

<template>
  <section class="surface health-card">
    <header class="module-head"><div><h2>项目健康度</h2><p>根据进度、延期和工时偏差自动判断。</p></div><span class="module-count">{{items.length}} 个项目</span></header>
    <div v-if="items.length" class="health-summary"><span><i class="normal"></i>正常 {{summary.normal}}</span><span><i class="attention"></i>关注 {{summary.attention}}</span><span><i class="risk"></i>风险 {{summary.risk}}</span></div>
    <div v-if="items.length" class="health-list" tabindex="0" role="region" aria-label="相关项目健康度，可滚动查看全部项目">
      <button v-for="item in items" :key="item.project_id" class="health-item" @click="emit('project',item.project_id)"><span class="health-dot" :class="item.status"></span><span class="health-main"><strong>{{item.project_name}}</strong><small>{{item.reason}}</small></span><span class="health-progress">{{item.progress}}%</span><span class="health-status" :class="item.status">{{labels[item.status]}}</span></button>
    </div>
    <div v-else class="compact-empty">暂无项目健康数据</div>
  </section>
</template>

<style scoped>
.health-card { display: flex; min-width: 0; min-height: 0; flex-direction: column; overflow: hidden; padding: 24px; }
.module-head,.health-summary { flex-shrink: 0; }
.module-head { display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
.module-head h2 { margin: 0; color: #1f2f43; font-size: 20px; font-weight: 650; line-height: 1.5; }
.module-head p { margin: 8px 0 0; color: #6f7f92; font-size: 14px; line-height: 1.6; }
.module-count { flex: 0 0 auto; border: 1px solid #e4eaf0; border-radius: 8px; background: #f7f9fb; padding: 6px 10px; color: #5e738b; font-size: 13px; }
.health-summary { display: flex; flex-wrap: wrap; gap: 12px 24px; margin-top: 20px; border-radius: 9px; background: #f6f8fa; padding: 12px 14px; color: #5f7389; font-size: 13px; }
.health-summary span { display: flex; align-items: center; gap: 8px; }
.health-summary i { width: 7px; height: 7px; border-radius: 50%; background: #57846f; }
.health-summary i.attention { background: #bd9150; }
.health-summary i.risk { background: #bb645e; }
.health-list { display: flex; min-height: 0; flex: 1 1 auto; flex-direction: column; overflow: auto; margin-top: 8px; scrollbar-gutter: stable; overscroll-behavior: contain; }
.health-item { display: grid; width: 100%; min-width: 0; flex-shrink: 0; grid-template-columns: 8px minmax(0,1fr) auto; align-items: center; gap: 8px 10px; border: 0; border-top: 1px solid #e9edf2; background: transparent; padding: 16px 4px; text-align: left; cursor: pointer; }
.health-main { grid-row: span 2; }
.health-progress { grid-column: 3; grid-row: 1; }
.health-status { grid-column: 3; grid-row: 2; }
.health-item:first-child { border-top: 0; }
.health-item:hover { border-radius: 8px; background: #f6f9fb; }
.health-dot { width: 8px; height: 8px; border-radius: 50%; background: #57846f; }
.health-dot.attention { background: #bd9150; }
.health-dot.risk,.health-dot.delayed { background: #bb645e; }
.health-main { display: flex; min-width: 0; flex-direction: column; gap: 6px; }
.health-main strong { overflow: hidden; color: #2d3e52; font-size: 15px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; line-height: 1.5; }
.health-main small { color: #6d7e91; font-size: 13px; line-height: 1.5; overflow-wrap: anywhere; }
.health-progress { color: #52677e; font-size: 14px; font-weight: 600; text-align: right; font-variant-numeric: tabular-nums; }
.health-status { border-radius: 6px; background: #eaf5f0; padding: 5px 8px; color: #437762; font-size: 12px; text-align: center; }
.health-status.attention { background: #faf2e5; color: #936a32; }
.health-status.risk,.health-status.delayed { background: #fbecea; color: #ac514c; }
.compact-empty { display: grid; min-height: 130px; flex: 1; place-items: center; color: #708095; font-size: 14px; }
button:focus-visible,.health-list:focus-visible { outline: 2px solid #527fa6; outline-offset: -2px; }
@media(max-width:1440px) { .health-card { padding: 20px; } }
</style>
