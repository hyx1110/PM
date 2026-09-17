<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deleteNotification,
  deleteReadNotifications,
  getNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '@/api/notification'
import type { AppNotification } from '@/types/notification'
import { formatDateTime } from '@/utils/format'
import { useNotificationStore } from '@/stores/notification'

const notificationStore = useNotificationStore()
const loading = ref(false)
const rows = ref<AppNotification[]>([]), total = ref(0)
const query = reactive({ page: 1, page_size: 20, status: '' })

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
function levelClass(level: string) { return `level-${level}` }
onMounted(async () => {
  await Promise.all([load(), notificationStore.refreshUnreadCount()])
})
</script>

<template>
  <div class="page-shell">
    <header class="page-header"><div><h1 class="page-title">通知中心</h1><p class="page-subtitle">排期新增/变更、确认提醒、临期任务、延期和冲突消息统一归档。</p></div><div><el-button type="primary" plain @click="readAll">全部已读</el-button><el-button type="danger" plain @click="clearRead">清空已读</el-button></div></header>
    <section class="surface filter-bar"><el-radio-group v-model="query.status" @change="query.page=1;load()"><el-radio-button value="">全部</el-radio-button><el-radio-button value="unread">未读</el-radio-button><el-radio-button value="read">已读</el-radio-button></el-radio-group></section>
    <section class="surface notifications" v-loading="loading">
      <article v-for="item in rows" :key="item.id" class="notification" :class="[{ unread: item.status==='unread' }, levelClass(item.level)]" role="button" tabindex="0" @click="read(item)" @keydown.enter="read(item)">
        <span class="indicator"></span><span class="message"><strong>{{ item.title }}</strong><span>{{ item.content }}</span><small>{{ formatDateTime(item.created_at) }} · {{ (item.delivered_channels || []).join(' / ') || '待投递' }}</small></span><span class="notification-actions"><el-tag v-if="item.status==='unread'" size="small">未读</el-tag><el-button link type="danger" @click.stop="remove(item)">删除</el-button></span>
      </article>
      <el-empty v-if="!rows.length" description="暂无通知"/>
      <div class="table-footer"><el-pagination v-model:current-page="query.page" :page-size="query.page_size" layout="total, prev, pager, next" :total="total" @change="load"/></div>
    </section>
  </div>
</template>

<style scoped>
.page-header>div:last-child{display:flex;gap:10px}.notifications{overflow:hidden;padding:8px 18px 16px}.notification{display:flex;width:100%;align-items:flex-start;gap:13px;border:0;border-bottom:1px solid #edf0f3;background:#fff;padding:17px 6px;text-align:left;cursor:pointer}.notification:hover{background:#fafbfd}.notification.unread{background:#f6f9fc}.indicator{width:8px;height:8px;flex:0 0 8px;margin-top:5px;border-radius:50%;background:#9aa6b4}.notification.unread .indicator{background:#4777a6;box-shadow:0 0 0 4px #e5eef7}.notification.level-warning .indicator{background:#c58a38}.notification.level-error .indicator{background:#b84e4e}.message{display:flex;min-width:0;flex:1;flex-direction:column}.message strong{color:#344156;font-size:13px}.message>span{margin-top:6px;color:#6d798a;font-size:12px;line-height:1.6}.message small{margin-top:7px;color:#a1a9b4;font-size:10px}.notification-actions{display:flex;align-items:center;gap:8px}.hint{margin-left:10px;color:#959fac;font-size:11px}
</style>
