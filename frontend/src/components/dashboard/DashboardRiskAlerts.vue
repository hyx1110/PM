<script setup lang="ts">
import { Warning } from '@element-plus/icons-vue'
import type { DashboardRiskAlert } from '@/types/report'

defineProps<{ items: DashboardRiskAlert[]; embedded?: boolean }>()
const emit = defineEmits<{ select: [item: DashboardRiskAlert] }>()
</script>

<template>
  <section class="risk-card" :class="{surface:!embedded,embedded}">
    <header class="module-head"><h2 v-if="!embedded">需要关注</h2><span class="risk-count">共 {{items.length}} 项关注事项</span></header>
    <div v-if="items.length" class="risk-list" tabindex="0" role="region" aria-label="需要关注的事项，可滚动查看">
      <el-tooltip v-for="item in items" :key="item.id" :content="item.detail || item.title" placement="top" :show-after="280">
        <button class="risk-item" @click="emit('select',item)"><span class="risk-icon" :class="item.severity"><el-icon><Warning /></el-icon></span><span><strong>{{item.title}}</strong><small>{{item.project_name || '系统事项'}}{{item.task_name?` · ${item.task_name}`:''}}</small></span></button>
      </el-tooltip>
    </div>
    <div v-else class="compact-empty">当前没有需要特别关注的异常</div>
  </section>
</template>

<style scoped>
.risk-card { display: flex; min-width: 0; min-height: 0; flex-direction: column; overflow: hidden; padding: 24px; }
.risk-card.embedded { padding: 0; }
.embedded .module-head { justify-content: flex-end; }
.module-head { flex-shrink: 0; }
.module-head { display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
.module-head h2 { margin: 0; color: #1f2f43; font-size: 20px; font-weight: 650; line-height: 1.5; }
.risk-count { display: grid; min-width: 28px; height: 28px; place-items: center; padding: 0 7px; border-radius: 14px; background: #fbecea; color: #aa504b; font-size: 13px; font-weight: 650; }
.risk-list { display: flex; min-height: 0; flex: 1; flex-direction: column; overflow: auto; margin-top: 16px; overscroll-behavior: contain; }
.risk-item { display: flex; width: 100%; min-width: 0; flex-shrink: 0; align-items: flex-start; gap: 12px; border: 0; border-top: 1px solid #e9edf2; background: transparent; padding: 16px 4px; text-align: left; cursor: pointer; }
.risk-item:first-child { border-top: 0; }
.risk-item:hover { border-radius: 8px; background: #f6f9fb; }
.risk-icon { display: grid; width: 36px; height: 36px; flex: 0 0 36px; place-items: center; border-radius: 10px; background: #faf2e5; color: #936a32; font-size: 18px; }
.risk-icon.danger { background: #fbecea; color: #ac514c; }
.risk-item > span:last-child { display: flex; min-width: 0; flex-direction: column; gap: 6px; }
.risk-item strong { color: #2d3e52; font-size: 15px; font-weight: 600; line-height: 1.6; overflow-wrap: anywhere; }
.risk-item small { overflow: hidden; color: #6d7e91; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; line-height: 1.5; }
.compact-empty { display: grid; min-height: 0; flex: 1; place-items: center; color: #708095; font-size: 14px; }
button:focus-visible,.risk-list:focus-visible { outline: 2px solid #527fa6; outline-offset: -2px; }
@media(max-width:1440px) { .risk-card { padding: 20px; } }
</style>
