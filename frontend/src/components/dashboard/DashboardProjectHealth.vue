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
    <header class="module-head"><div><span class="eyebrow">PROJECT HEALTH</span><h2>项目健康度</h2><p>根据进度、延期和工时偏差自动判断。</p></div><span class="module-count">{{items.length}} 个项目</span></header>
    <div v-if="items.length" class="health-summary"><span><i class="normal"></i>正常 {{summary.normal}}</span><span><i class="attention"></i>关注 {{summary.attention}}</span><span><i class="risk"></i>风险 {{summary.risk}}</span></div>
    <div v-if="items.length" class="health-list">
      <button v-for="item in items" :key="item.project_id" class="health-item" @click="emit('project',item.project_id)"><span class="health-dot" :class="item.status"></span><span class="health-main"><strong>{{item.project_name}}</strong><small>{{item.reason}}</small></span><span class="health-progress">{{item.progress}}%</span><span class="health-status" :class="item.status">{{labels[item.status]}}</span></button>
    </div>
    <div v-else class="compact-empty">暂无项目健康数据</div>
  </section>
</template>

<style scoped>
.health-card{height:100%;padding:19px 20px}.module-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}.module-head h2{margin:6px 0 0;color:#1f2f43;font-size:17px;font-weight:680}.module-head p{margin:6px 0 0;color:#8592a2;font-size:10px}.eyebrow{color:#7890a7;font-size:9px;font-weight:780;letter-spacing:.15em}.module-count{flex:0 0 auto;border:1px solid #e4eaf0;border-radius:8px;background:#f7f9fb;padding:5px 7px;color:#748398;font-size:8px}.health-summary{display:flex;gap:13px;margin-top:13px;border-radius:9px;background:#f6f8fa;padding:8px 9px;color:#718095;font-size:8px}.health-summary span{display:flex;align-items:center;gap:5px}.health-summary i{width:6px;height:6px;border-radius:50%;background:#57846f}.health-summary i.attention{background:#bd9150}.health-summary i.risk{background:#bb645e}.health-list{display:flex;flex-direction:column;margin-top:7px}.health-item{display:grid;width:100%;min-width:0;grid-template-columns:7px minmax(0,1fr) 38px 38px;align-items:center;gap:8px;border:0;border-top:1px solid #e9edf2;background:transparent;padding:10px 2px;text-align:left;cursor:pointer;transition:background .15s}.health-item:first-child{border-top:0}.health-item:hover{border-radius:8px;background:#f6f9fb}.health-dot{width:7px;height:7px;border-radius:50%;background:#57846f}.health-dot.attention{background:#bd9150}.health-dot.risk,.health-dot.delayed{background:#bb645e}.health-main{display:flex;min-width:0;flex-direction:column}.health-main strong,.health-main small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.health-main strong{color:#2d3e52;font-size:10px;font-weight:660}.health-main small{margin-top:4px;color:#8491a0;font-size:9px}.health-progress{color:#586a7f;font-size:9px;font-weight:620;text-align:right}.health-status{border-radius:6px;background:#eaf5f0;padding:4px 5px;color:#437762;font-size:8px;text-align:center}.health-status.attention{background:#faf2e5;color:#936a32}.health-status.risk,.health-status.delayed{background:#fbecea;color:#ac514c}.compact-empty{display:grid;height:165px;place-items:center;color:#8d99a7;font-size:11px}
</style>
