<script setup lang="ts">
import { computed } from 'vue'
import type { DashboardTaskItem } from '@/types/report'
import { formatDate } from '@/utils/format'

const visible = defineModel<boolean>({ required: true })
const props = defineProps<{ task?: DashboardTaskItem }>()
const emit = defineEmits<{ openExecutions: [task: DashboardTaskItem] }>()
const statusLabel: Record<string, string> = { not_started: '未开始', running: '进行中', completed: '已完成', delayed: '已逾期' }
const varianceText = computed(() => {
  if (!props.task) return '—'
  if (props.task.deviation_hours === 0) return '与预计一致'
  return `${props.task.deviation_hours > 0 ? '超出' : '节省'} ${Math.abs(props.task.deviation_hours)}h`
})
</script>

<template>
  <el-drawer v-model="visible" title="任务详情" size="430px" destroy-on-close>
    <div v-if="task" class="drawer-content">
      <header><span>{{task.project_name}}</span><h2>{{task.name}}</h2><div><el-tag size="small" effect="plain">{{statusLabel[task.status] || task.status}}</el-tag><small>{{task.owner_name}}</small></div></header>
      <section class="progress-panel"><div><span>当前进度</span><strong>{{task.progress}}%</strong></div><el-progress :percentage="task.progress" :stroke-width="7" :show-text="false" color="#6488a9"/></section>
      <section class="detail-grid"><article><span>计划工期</span><strong>{{formatDate(task.planned_start)}} 至 {{formatDate(task.planned_end)}}</strong></article><article><span>实际工期</span><strong>{{formatDate(task.actual_start)}} 至 {{formatDate(task.actual_end)}}</strong></article><article><span>预计工时</span><strong>{{task.estimated_hours}}h</strong></article><article><span>累计实际工时</span><strong>{{task.actual_hours}}h</strong></article><article><span>工时偏差</span><strong :class="`variance-${task.variance}`">{{varianceText}}</strong></article><article><span>执行记录</span><strong>{{task.record_count}} 条</strong></article></section>
      <section v-if="task.description || task.remark" class="text-panel"><div v-if="task.description"><span>任务描述</span><p>{{task.description}}</p></div><div v-if="task.remark"><span>备注</span><p>{{task.remark}}</p></div></section>
    </div>
    <template #footer><el-button @click="visible=false">关闭</el-button><el-button v-if="task" type="primary" @click="emit('openExecutions',task)">查看执行记录</el-button></template>
  </el-drawer>
</template>

<style scoped>
.drawer-content{display:flex;flex-direction:column;gap:16px}.drawer-content header{border-bottom:1px solid #edf0f3;padding-bottom:16px}.drawer-content header>span{color:#8493a3;font-size:11px}.drawer-content h2{margin:6px 0 10px;color:#273548;font-size:20px}.drawer-content header div{display:flex;align-items:center;gap:9px}.drawer-content header small{color:#8d98a6}.progress-panel{border-radius:13px;background:#f7f9fb;padding:14px}.progress-panel>div{display:flex;justify-content:space-between;margin-bottom:9px;color:#728092;font-size:11px}.progress-panel strong{color:#315f8e;font-size:15px}.detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.detail-grid article{display:flex;min-height:69px;flex-direction:column;justify-content:center;border:1px solid #edf0f3;border-radius:11px;padding:11px}.detail-grid span,.text-panel span{color:#939daa;font-size:10px}.detail-grid strong{margin-top:6px;color:#39475a;font-size:11px}.variance-good{color:#4f806c!important}.variance-warning{color:#9a7138!important}.variance-severe{color:#b25752!important}.text-panel{display:flex;flex-direction:column;gap:13px;border-top:1px solid #edf0f3;padding-top:15px}.text-panel p{margin:5px 0 0;color:#59687a;font-size:12px;line-height:1.7}
</style>
