<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { Refresh } from '@element-plus/icons-vue'
import type { DashboardDayItem, DashboardMyDay } from '@/types/report'
import { BEIJING_TIMEZONE, beijingNow } from '@/utils/time'

const props = defineProps<{ day?: DashboardMyDay; loading: boolean; failed: boolean }>()
const emit = defineEmits<{ refresh: [] }>()
const now = ref(beijingNow())
const selected = ref<DashboardDayItem>()
const drawerVisible = ref(false)
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => { timer = setInterval(() => { now.value = beijingNow() }, 60000) })
onUnmounted(() => { if (timer) clearInterval(timer) })
// ORM datetime values are naive Beijing time, not the browser's local zone.
const parse = (value: string) => /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value)
  ? dayjs(value).tz(BEIJING_TIMEZONE) : dayjs.tz(value, BEIJING_TIMEZONE)
const today = computed(() => now.value.format('YYYY-MM-DD'))
const stale = computed(() => !!props.day && props.day.date !== today.value)
const pending = (item: DashboardDayItem) => item.kind === 'booking' && ['pending', 'changed'].includes(item.status)
const items = computed(() => (props.day?.items || [])
  .filter(item => !pending(item) || parse(item.end_time).isAfter(now.value))
  .sort((a, b) => parse(a.start_time).valueOf() - parse(b.start_time).valueOf() || parse(a.end_time).valueOf() - parse(b.end_time).valueOf() || a.id.localeCompare(b.id)))
const pendingCount = computed(() => items.value.filter(pending).length)
const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
const dateLabel = computed(() => {
  const value = dayjs(props.day?.date || today.value)
  return `${value.format('MM月DD日')} · ${weekdays[value.day()]}`
})
function phase(item: DashboardDayItem) {
  if (pending(item)) return parse(item.end_time).isAfter(now.value)
    ? { label: '待确认', tone: 'pending' } : { label: '预约已过期', tone: 'past' }
  if (!parse(item.end_time).isAfter(now.value)) return { label: '时段已结束', tone: 'past' }
  if (!parse(item.start_time).isAfter(now.value)) return { label: '当前时段', tone: 'current' }
  return { label: '未到时间', tone: 'upcoming' }
}
function timeLabel(item: DashboardDayItem, end = false) {
  const value = parse(end ? item.end_time : item.start_time)
  const date = props.day?.date || today.value
  if (value.format('YYYY-MM-DD') < date) return '00:00'
  if (value.format('YYYY-MM-DD') > date) return '24:00'
  return value.format('HH:mm')
}
function fullPeriod(item: DashboardDayItem) {
  return `${parse(item.start_time).format('YYYY-MM-DD HH:mm')} 至 ${parse(item.end_time).format('YYYY-MM-DD HH:mm')}`
}
function open(item: DashboardDayItem) { selected.value = item; drawerVisible.value = true }
watch(() => props.day, () => {
  now.value = beijingNow()
  if (!selected.value) return
  selected.value = props.day?.items.find(item => item.id === selected.value?.id)
  if (!selected.value) drawerVisible.value = false
})
</script>

<template>
  <section class="surface day-card">
    <header><div><h2>我的今日日程</h2><p>{{dateLabel}} · 北京时间</p></div><button class="refresh" :disabled="loading" aria-label="刷新首页及今日日程" @click="emit('refresh')"><el-icon :class="{'is-loading':loading}"><Refresh /></el-icon></button></header>
    <p v-if="failed || stale || !day" class="day-warning" role="status">{{failed ? '刷新失败，当前可能为旧数据，请重试。' : stale ? '显示的是上一日数据，请刷新。' : '日程数据暂未提供，请刷新。'}}</p>
    <div v-if="day" class="day-summary"><span>{{items.length}} 项安排</span><span v-if="pendingCount">含 {{pendingCount}} 项待确认，尚未占用时间</span><span v-else>仅本人日程</span></div>
    <div v-if="items.length" class="day-list" tabindex="0" role="region" aria-label="今日日程，按时间从上到下排列，可滚动查看">
      <button v-for="item in items" :key="item.id" class="day-item" :class="phase(item).tone" @click="open(item)">
        <span class="time-column"><strong>{{timeLabel(item)}}</strong><small>{{timeLabel(item,true)}}</small></span>
        <span class="timeline-rail" aria-hidden="true"><i></i></span>
        <span class="event-body"><span class="event-meta"><span>{{item.kind==='booking' ? '项目预约' : '个人安排'}}</span><span class="event-state">{{phase(item).label}}</span></span><strong>{{item.title}}</strong><small>{{item.project_name || item.remark || '点击查看详情'}}</small></span>
      </button>
    </div>
    <div v-else class="compact-empty"><strong>{{day ? '今天暂无日程安排' : '暂无日程数据'}}</strong><span>项目预约和个人安排会按时间展示在这里。</span></div>
    <footer>从早到晚排列 · 点击查看详情</footer>
    <el-drawer v-model="drawerVisible" title="我的日程详情" size="min(520px, 100vw)" append-to-body>
      <template v-if="selected"><h3 class="detail-title">{{selected.title}}</h3><el-descriptions :column="1" border>
        <el-descriptions-item label="来源">{{selected.kind==='booking' ? '项目预约' : '个人安排'}}</el-descriptions-item>
        <el-descriptions-item v-if="selected.project_name" label="项目">{{selected.project_name}}</el-descriptions-item>
        <el-descriptions-item label="时间（北京）">{{fullPeriod(selected)}}</el-descriptions-item>
        <el-descriptions-item label="时段状态">{{phase(selected).label}}</el-descriptions-item>
        <el-descriptions-item label="备注"><span class="detail-remark">{{selected.remark || '—'}}</span></el-descriptions-item>
      </el-descriptions><p v-if="pending(selected)" class="detail-hint">此预约尚未确认，不代表已占用。请在左侧“待处理事项 → 审批 / 预约”中查看并处理。</p><p class="detail-hint">此处展示日程时间，不代表任务的实际执行状态或实际工时。</p></template>
    </el-drawer>
  </section>
</template>

<style scoped>
.day-card { display: flex; min-width: 0; min-height: 0; flex-direction: column; overflow: hidden; padding: 24px; }
header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; flex-shrink: 0; }
h2 { margin: 0; color: #1f2f43; font-size: 20px; font-weight: 650; line-height: 1.5; }
header p { margin: 8px 0 0; color: #6f7f92; font-size: 14px; line-height: 1.6; }
.refresh { display: grid; width: 32px; height: 32px; flex-shrink: 0; place-items: center; border: 1px solid #e4eaf0; border-radius: 8px; background: #f7f9fb; color: #60758d; font-size: 16px; cursor: pointer; }
.refresh:disabled { cursor: wait; opacity: .6; }
.day-warning { flex-shrink: 0; margin: 10px 0 0; color: #9d6833; font-size: 13px; }
.day-summary { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 4px 12px; flex-shrink: 0; margin: 18px 0 10px; padding: 10px 12px; border-radius: 8px; background: #f5f8fa; color: #677c8e; font-size: 12px; }
.day-list { min-height: 0; flex: 1; overflow: auto; overscroll-behavior: contain; scrollbar-gutter: stable; }
.day-item { display: grid; width: 100%; grid-template-columns: 46px 18px minmax(0,1fr); border: 0; background: transparent; padding: 0 4px; text-align: left; cursor: pointer; }
.time-column { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; padding-top: 15px; font-variant-numeric: tabular-nums; }
.time-column strong { color: #40576f; font-size: 14px; font-weight: 600; }
.time-column small { color: #8390a0; font-size: 12px; }
.timeline-rail { position: relative; display: flex; justify-content: center; }
.timeline-rail::before { position: absolute; content: ''; top: 0; bottom: 0; width: 1px; background: #e0e7ee; }
.day-item:first-child .timeline-rail::before { top: 23px; }
.day-item:last-child .timeline-rail::before { bottom: calc(100% - 23px); }
.timeline-rail i { z-index: 1; width: 8px; height: 8px; margin-top: 20px; border: 2px solid #fff; border-radius: 50%; background: #a2b7c9; box-shadow: 0 0 0 1px #d0dce6; box-sizing: content-box; }
.event-body { display: flex; min-width: 0; flex-direction: column; gap: 5px; margin: 5px 0 8px 8px; padding: 10px 12px; border: 1px solid #e5ebf1; border-radius: 10px; background: #f8fafc; }
.day-item:hover .event-body { border-color: #abc4d9; }
.event-meta { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 4px 10px; color: #738497; font-size: 12px; }
.event-body > strong { color: #2d3e52; font-size: 15px; font-weight: 600; overflow-wrap: anywhere; }
.event-body > small { overflow: hidden; color: #738497; font-size: 13px; white-space: nowrap; text-overflow: ellipsis; }
.current .timeline-rail i { background: #4f7fa8; box-shadow: 0 0 0 3px #e9f0f6; }
.current .event-body { border-color: #bfd1e1; background: #f0f6fb; }
.current .event-state { color: #386990; font-weight: 600; }
.pending .event-body { border-style: dashed; background: #fafafa; }
.pending .event-state { color: #966e35; }
.past .event-body { background: #fff; }
.compact-empty { display: flex; min-height: 0; flex: 1; flex-direction: column; justify-content: center; align-items: center; gap: 8px; padding: 16px; color: #708095; font-size: 13px; text-align: center; }
.compact-empty strong { color: #62768b; font-size: 14px; font-weight: 500; }
footer { flex-shrink: 0; border-top: 1px solid #edf1f4; padding-top: 12px; color: #748396; font-size: 12px; }
.detail-title { margin: 0 0 20px; color: #25394f; overflow-wrap: anywhere; }
.detail-remark { white-space: pre-wrap; overflow-wrap: anywhere; }
.detail-hint { color: #6f7f92; font-size: 14px; line-height: 1.7; }
button:focus-visible,.day-list:focus-visible { outline: 2px solid #527fa6; outline-offset: -2px; }
@media(max-width:1440px) { .day-card { padding: 20px; } }
</style>
