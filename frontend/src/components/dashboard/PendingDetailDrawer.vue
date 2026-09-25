<script setup lang="ts">
import dayjs from 'dayjs'
import type { DashboardPendingItem } from '@/types/report'
import { formatDateTime } from '@/utils/format'

const visible = defineModel<boolean>({ required: true })
defineProps<{ item?: DashboardPendingItem; loading?: boolean }>()
const emit = defineEmits<{ approve: [item: DashboardPendingItem]; reject: [item: DashboardPendingItem]; openProject: [id: number] }>()
</script>

<template>
  <el-drawer v-model="visible" title="待处理详情" size="430px" destroy-on-close>
    <div v-if="item" class="drawer-content">
      <header><el-tag size="small" effect="plain">{{item.type_label}}</el-tag><h2>{{item.title}}</h2><p>{{item.project_name}}</p></header>
      <section class="detail-list"><article><span>申请人</span><strong>{{item.applicant_name}}</strong></article><article v-if="item.booking_user_name"><span>预约人员</span><strong>{{item.booking_user_name}}</strong></article><article><span>发起时间</span><strong>{{formatDateTime(item.created_at)}}</strong></article><article v-if="item.start_time"><span>预约时间</span><strong>{{dayjs(item.start_time).format('YYYY-MM-DD HH:mm')}} 至 {{dayjs(item.end_time).format('HH:mm')}}</strong></article><article><span>申请内容</span><p>{{item.content}}</p></article></section>
      <el-alert title="该操作将直接使用系统现有审批或预约确认流程，并同步通知相关人员。" type="info" :closable="false" show-icon/>
    </div>
    <template #footer><el-button v-if="item" text type="primary" @click="emit('openProject',item.project_id)">查看项目</el-button><span class="footer-spacer"></span><el-button @click="visible=false">关闭</el-button><template v-if="item?.actionable"><el-button :disabled="loading" @click="emit('reject',item)">驳回</el-button><el-button type="primary" :loading="loading" @click="emit('approve',item)">确认</el-button></template></template>
  </el-drawer>
</template>

<style scoped>
.drawer-content{display:flex;flex-direction:column;gap:18px}.drawer-content header{border-bottom:1px solid #edf0f3;padding-bottom:16px}.drawer-content h2{margin:9px 0 5px;color:#273548;font-size:20px}.drawer-content header p{margin:0;color:#8793a2;font-size:11px}.detail-list{display:flex;flex-direction:column}.detail-list article{display:grid;grid-template-columns:75px minmax(0,1fr);gap:12px;border-bottom:1px solid #f0f2f4;padding:12px 0}.detail-list span{color:#939daa;font-size:10px}.detail-list strong,.detail-list p{margin:0;color:#455367;font-size:12px;line-height:1.6}.footer-spacer{flex:1}
</style>
