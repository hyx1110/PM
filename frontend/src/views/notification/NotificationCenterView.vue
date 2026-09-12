<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deleteNotification,
  deleteReadNotifications,
  getNotificationPreference,
  getNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  updateNotificationPreference,
} from '@/api/notification'
import type { AppNotification, NotificationPreference } from '@/types/notification'
import { formatDateTime } from '@/utils/format'
import { useNotificationStore } from '@/stores/notification'

const notificationStore = useNotificationStore()
const loading = ref(false), saving = ref(false), preferenceVisible = ref(false)
const rows = ref<AppNotification[]>([]), total = ref(0)
const query = reactive({ page: 1, page_size: 20, status: '' })
const preference = reactive<NotificationPreference>({ in_app_enabled: true, email_enabled: false, wecom_enabled: false, dingtalk_enabled: false, upcoming_hours: 24 })

async function load() { loading.value = true; try { const page = await getNotifications(query); rows.value = page.items; total.value = page.total } finally { loading.value = false } }
async function read(item: AppNotification) {
  if (item.status !== 'unread') return
  await markNotificationRead(item.id)
  item.status = 'read'
  notificationStore.markOneRead()
  await notificationStore.refreshUnreadCount()
  if (query.status === 'unread') await load()
}
async function readAll() {
  const result = await markAllNotificationsRead()
  notificationStore.markAllRead()
  await notificationStore.refreshUnreadCount()
  ElMessage.success(`已标记 ${result.updated} 条通知`)
  await load()
}
async function remove(item: AppNotification) {
  await ElMessageBox.confirm('确认删除这条通知吗？','删除通知',{type:'warning',confirmButtonText:'确认删除'})
  await deleteNotification(item.id)
  if (item.status === 'unread') notificationStore.markOneRead()
  await notificationStore.refreshUnreadCount()
  ElMessage.success('通知已删除')
  await load()
}
async function clearRead() { await ElMessageBox.confirm('确认清空全部已读通知吗？未读通知会保留。','清空已读通知',{type:'warning',confirmButtonText:'确认清空'});const result=await deleteReadNotifications();ElMessage.success(`已清空 ${result.deleted} 条已读通知`);await load() }
async function openPreference() { Object.assign(preference, await getNotificationPreference()); preferenceVisible.value = true }
async function savePreference() { saving.value = true; try { Object.assign(preference, await updateNotificationPreference(preference)); ElMessage.success('通知偏好已保存'); preferenceVisible.value = false } finally { saving.value = false } }
function levelClass(level: string) { return `level-${level}` }
onMounted(async () => {
  await Promise.all([load(), notificationStore.refreshUnreadCount()])
})
</script>

<template>
  <div class="page-shell">
    <header class="page-header"><div><h1 class="page-title">通知中心</h1><p class="page-subtitle">排期新增/变更、确认提醒、临期任务、延期和冲突消息统一归档。</p></div><div><el-button @click="openPreference">通知偏好</el-button><el-button type="primary" plain @click="readAll">全部已读</el-button><el-button type="danger" plain @click="clearRead">清空已读</el-button></div></header>
    <section class="surface filter-bar"><el-radio-group v-model="query.status" @change="query.page=1;load()"><el-radio-button value="">全部</el-radio-button><el-radio-button value="unread">未读</el-radio-button><el-radio-button value="read">已读</el-radio-button></el-radio-group></section>
    <section class="surface notifications" v-loading="loading">
      <article v-for="item in rows" :key="item.id" class="notification" :class="[{ unread: item.status==='unread' }, levelClass(item.level)]" role="button" tabindex="0" @click="read(item)" @keydown.enter="read(item)">
        <span class="indicator"></span><span class="message"><strong>{{ item.title }}</strong><span>{{ item.content }}</span><small>{{ formatDateTime(item.created_at) }} · {{ (item.delivered_channels || []).join(' / ') || '待投递' }}</small></span><span class="notification-actions"><el-tag v-if="item.status==='unread'" size="small">未读</el-tag><el-button link type="danger" @click.stop="remove(item)">删除</el-button></span>
      </article>
      <el-empty v-if="!rows.length" description="暂无通知"/>
      <div class="table-footer"><el-pagination v-model:current-page="query.page" :page-size="query.page_size" layout="total, prev, pager, next" :total="total" @change="load"/></div>
    </section>
    <el-dialog v-model="preferenceVisible" title="通知偏好" width="520px"><el-form label-position="left" label-width="130px"><el-form-item label="站内通知"><el-switch v-model="preference.in_app_enabled"/></el-form-item><el-form-item label="电子邮件"><el-switch v-model="preference.email_enabled"/><span class="hint">需管理员配置 SMTP 且账号已填写邮箱</span></el-form-item><el-form-item label="企业微信机器人"><el-switch v-model="preference.wecom_enabled"/><span class="hint">需配置企业微信 Webhook</span></el-form-item><el-form-item label="钉钉机器人"><el-switch v-model="preference.dingtalk_enabled"/><span class="hint">需配置钉钉 Webhook</span></el-form-item><el-form-item label="临期提醒时间"><el-input-number v-model="preference.upcoming_hours" :min="1" :max="168"/><span class="hint">小时</span></el-form-item></el-form><template #footer><el-button @click="preferenceVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="savePreference">保存</el-button></template></el-dialog>
  </div>
</template>

<style scoped>
.page-header>div:last-child{display:flex;gap:10px}.notifications{overflow:hidden;padding:8px 18px 16px}.notification{display:flex;width:100%;align-items:flex-start;gap:13px;border:0;border-bottom:1px solid #edf0f3;background:#fff;padding:17px 6px;text-align:left;cursor:pointer}.notification:hover{background:#fafbfd}.notification.unread{background:#f6f9fc}.indicator{width:8px;height:8px;flex:0 0 8px;margin-top:5px;border-radius:50%;background:#9aa6b4}.notification.unread .indicator{background:#4777a6;box-shadow:0 0 0 4px #e5eef7}.notification.level-warning .indicator{background:#c58a38}.notification.level-error .indicator{background:#b84e4e}.message{display:flex;min-width:0;flex:1;flex-direction:column}.message strong{color:#344156;font-size:13px}.message>span{margin-top:6px;color:#6d798a;font-size:12px;line-height:1.6}.message small{margin-top:7px;color:#a1a9b4;font-size:10px}.notification-actions{display:flex;align-items:center;gap:8px}.hint{margin-left:10px;color:#959fac;font-size:11px}
</style>
