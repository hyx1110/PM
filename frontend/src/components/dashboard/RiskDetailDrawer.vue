<script setup lang="ts">
import type { DashboardRiskAlert } from '@/types/report'
import { formatDateTime } from '@/utils/format'

const visible = defineModel<boolean>({ required: true })
defineProps<{ item?: DashboardRiskAlert }>()
const emit = defineEmits<{ openProject: [id: number]; openTask: [id: number] }>()
</script>

<template>
  <el-drawer v-model="visible" title="关注事项" size="min(560px, 100vw)" destroy-on-close>
    <div v-if="item" class="drawer-content">
      <header><span class="severity" :class="item.severity">{{item.severity==='danger'?'高优先级':'需要关注'}}</span><h2>{{item.title}}</h2><p>{{item.project_name}}{{item.task_name?` · ${item.task_name}`:''}}</p></header>
      <section><span>详细说明</span><p>{{item.detail || '暂无更多说明'}}</p></section><section><span>发现时间</span><p>{{formatDateTime(item.occurred_at)}}</p></section>
    </div>
    <template #footer><el-button @click="visible=false">关闭</el-button><el-button v-if="item?.project_id" @click="emit('openProject',item.project_id)">查看项目</el-button><el-button v-if="item?.task_id" type="primary" @click="emit('openTask',item.task_id)">查看相关任务</el-button></template>
  </el-drawer>
</template>

<style scoped>
.drawer-content { display: flex; flex-direction: column; gap: 24px; }
.drawer-content header { border-bottom: 1px solid #e6ecf2; padding-bottom: 20px; }
.severity { display: inline-flex; border-radius: 7px; background: #faf3e7; padding: 6px 10px; color: #8b6630; font-size: 13px; }
.severity.danger { background: #fbeeed; color: #a44f49; }
.drawer-content h2 { margin: 14px 0 10px; color: #273548; font-size: 22px; line-height: 1.5; overflow-wrap: anywhere; }
.drawer-content header p,.drawer-content section p { margin: 0; color: #536980; font-size: 14px; line-height: 1.8; overflow-wrap: anywhere; }
.drawer-content section > span { display: block; margin-bottom: 10px; color: #697e95; font-size: 13px; }
</style>
