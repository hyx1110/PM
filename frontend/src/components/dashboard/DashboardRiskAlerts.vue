<script setup lang="ts">
import { computed, ref } from 'vue'
import { Warning } from '@element-plus/icons-vue'
import type { DashboardRiskAlert } from '@/types/report'

const props = defineProps<{ items: DashboardRiskAlert[] }>()
const emit = defineEmits<{ select: [item: DashboardRiskAlert] }>()
const expanded = ref(false)
const visibleItems = computed(() => expanded.value ? props.items : props.items.slice(0, 3))
</script>

<template>
  <section class="surface risk-card">
    <header class="module-head"><div><h2>需要关注</h2><p>优先查看延期、超时和待处理异常。</p></div><div class="head-actions"><span v-if="items.length" class="risk-count">{{items.length}}</span><button v-if="items.length>3" class="text-button" :aria-expanded="expanded" @click="expanded=!expanded">{{expanded?'收起':'查看更多'}}</button></div></header>
    <div v-if="visibleItems.length" class="risk-list">
      <el-tooltip v-for="item in visibleItems" :key="item.id" :content="item.detail || item.title" placement="top" :show-after="280">
        <button class="risk-item" @click="emit('select',item)"><span class="risk-icon" :class="item.severity"><el-icon><Warning /></el-icon></span><span><strong>{{item.title}}</strong><small>{{item.project_name || '系统事项'}}{{item.task_name?` · ${item.task_name}`:''}}</small></span></button>
      </el-tooltip>
    </div>
    <div v-else class="compact-empty">当前没有需要特别关注的异常</div>
  </section>
</template>

<style scoped>
.risk-card { min-width: 0; padding: 24px; }
.module-head { display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
.module-head h2 { margin: 0; color: #1f2f43; font-size: 20px; font-weight: 650; line-height: 1.5; }
.module-head p { margin: 8px 0 0; color: #6f7f92; font-size: 14px; line-height: 1.6; }
.head-actions { display: flex; align-items: center; gap: 12px; }
.risk-count { display: grid; min-width: 28px; height: 28px; place-items: center; padding: 0 7px; border-radius: 14px; background: #fbecea; color: #aa504b; font-size: 13px; font-weight: 650; }
.text-button { border: 0; border-radius: 6px; background: transparent; padding: 8px 0; color: #436d94; font-size: 13px; cursor: pointer; }
.risk-list { display: flex; flex-direction: column; margin-top: 16px; }
.risk-item { display: flex; width: 100%; min-width: 0; min-height: 108px; align-items: flex-start; gap: 16px; border: 0; border-top: 1px solid #e9edf2; background: transparent; padding: 22px 4px; text-align: left; cursor: pointer; }
.risk-item:first-child { border-top: 0; }
.risk-item:hover { border-radius: 8px; background: #f6f9fb; }
.risk-icon { display: grid; width: 36px; height: 36px; flex: 0 0 36px; place-items: center; border-radius: 10px; background: #faf2e5; color: #936a32; font-size: 18px; }
.risk-icon.danger { background: #fbecea; color: #ac514c; }
.risk-item > span:last-child { display: flex; min-width: 0; flex-direction: column; gap: 6px; }
.risk-item strong { color: #2d3e52; font-size: 15px; font-weight: 600; line-height: 1.6; overflow-wrap: anywhere; }
.risk-item small { overflow: hidden; color: #6d7e91; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; line-height: 1.5; }
.compact-empty { display: grid; min-height: 130px; place-items: center; color: #708095; font-size: 14px; }
button:focus-visible { outline: 2px solid #527fa6; outline-offset: 2px; }
@media(max-width:1440px) { .risk-card { padding: 20px; } }
</style>
