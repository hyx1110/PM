<script setup lang="ts">
import { computed, ref } from 'vue'
import { Warning } from '@element-plus/icons-vue'
import type { DashboardRiskAlert } from '@/types/report'

const props = defineProps<{ items: DashboardRiskAlert[] }>()
const emit = defineEmits<{ select: [item: DashboardRiskAlert] }>()
const expanded = ref(false)
const visibleItems = computed(() => props.items.slice(0, expanded.value ? 10 : 5))
</script>

<template>
  <section class="surface risk-card">
    <header class="module-head"><div><span class="eyebrow">ATTENTION</span><h2>需要关注</h2></div><div class="head-actions"><span v-if="items.length" class="risk-count">{{items.length}}</span><button v-if="items.length>5" class="text-button" @click="expanded=!expanded">{{expanded?'收起':'查看更多'}}</button></div></header>
    <div v-if="visibleItems.length" class="risk-list">
      <el-tooltip v-for="item in visibleItems" :key="item.id" :content="item.detail || item.title" placement="top" :show-after="280">
        <button class="risk-item" @click="emit('select',item)"><span class="risk-icon" :class="item.severity"><el-icon><Warning /></el-icon></span><span><strong>{{item.title}}</strong><small>{{item.project_name || '系统事项'}}{{item.task_name?` · ${item.task_name}`:''}}</small></span></button>
      </el-tooltip>
    </div>
    <div v-else class="compact-empty">当前没有需要特别关注的异常</div>
  </section>
</template>

<style scoped>
.risk-card{height:100%;padding:19px 20px}.module-head{display:flex;align-items:center;justify-content:space-between}.module-head h2{margin:6px 0 0;color:#1f2f43;font-size:17px;font-weight:680}.eyebrow{color:#7890a7;font-size:9px;font-weight:780;letter-spacing:.15em}.head-actions{display:flex;align-items:center;gap:6px}.risk-count{display:grid;min-width:22px;height:22px;place-items:center;border-radius:11px;background:#fbecea;color:#aa504b;font-size:9px;font-weight:700}.text-button{border:0;background:transparent;color:#557899;font-size:9px;font-weight:600;cursor:pointer}.risk-list{display:flex;flex-direction:column;margin-top:13px}.risk-item{display:flex;width:100%;min-width:0;align-items:center;gap:10px;border:0;border-top:1px solid #e9edf2;background:transparent;padding:10px 2px;text-align:left;cursor:pointer;transition:background .15s}.risk-item:first-child{border-top:0}.risk-item:hover{border-radius:8px;background:#f6f9fb}.risk-icon{display:grid;width:28px;height:28px;flex:0 0 28px;place-items:center;border-radius:9px;background:#faf2e5;color:#936a32}.risk-icon.danger{background:#fbecea;color:#ac514c}.risk-item>span:last-child{display:flex;min-width:0;flex-direction:column}.risk-item strong,.risk-item small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.risk-item strong{color:#2d3e52;font-size:10px;font-weight:650}.risk-item small{margin-top:4px;color:#8491a0;font-size:9px}.compact-empty{display:grid;height:165px;place-items:center;color:#8d99a7;font-size:11px}
</style>
