<script setup lang="ts">
import { computed } from 'vue'
import dayjs from 'dayjs'
import type { ScheduleDayMeta } from '@/types/work-calendar'

const props = defineProps<{
  days: string[]
  slots: string[]
  cellWidth: number
  dayMeta: Record<string, ScheduleDayMeta>
}>()

const endTick = computed(() => {
  const last = props.slots.at(-1) || '17:30'
  return dayjs(`2000-01-01 ${last}`).add(30, 'minute').format('HH:mm')
})
const ticks = computed(() => [...props.slots, endTick.value])
const dayWidth = computed(() => props.slots.length * props.cellWidth)

function isWorkingSlot(time: string) {
  return (time >= '08:30' && time < '12:00') || (time >= '13:00' && time < '17:30')
}

function intervalKind(day: string, time: string) {
  const kind = props.dayMeta[day]?.kind
  if (kind === 'holiday') return 'holiday'
  if (kind === 'weekend') return 'off-hours'
  return isWorkingSlot(time) ? 'work' : 'off-hours'
}

function intervalTitle(day: string, time: string, index: number) {
  const meta = props.dayMeta[day]
  const end = index < props.slots.length - 1 ? props.slots[index + 1] : endTick.value
  if (meta?.kind === 'holiday') return `${day} ${meta.name || '法定节假日'}，不可预约`
  if (meta?.kind === 'weekend') return `${day} 周末休息，不可预约`
  if (time >= '12:00' && time < '13:00') return `${day} ${time}–${end} 午休，不可预约`
  if (!isWorkingSlot(time)) return `${day} ${time}–${end} 非工作时间，不可预约`
  return `${day} ${time}–${end} 工作时间`
}
</script>

<template>
  <div class="timeline-header" :style="{ width: `${days.length * slots.length * cellWidth}px` }">
    <div class="day-row" :style="{ gridTemplateColumns: `repeat(${days.length}, ${dayWidth}px)` }">
      <div v-for="day in days" :key="day" class="day-cell" :class="`day-${dayMeta[day]?.kind || 'workday'}`">
        <strong>{{ dayjs(day).format('MM月DD日') }}</strong>
        <span>{{ ['周日','周一','周二','周三','周四','周五','周六'][dayjs(day).day()] }}</span>
        <em v-if="dayMeta[day]?.kind==='holiday'">法定节假日 · {{ dayMeta[day]?.name }}</em>
        <em v-else-if="dayMeta[day]?.kind==='workday'&&dayMeta[day]?.name" class="workday-note">调休工作日</em>
      </div>
    </div>
    <div class="axis-row">
      <div v-for="day in days" :key="day" class="time-axis" :style="{ width: `${dayWidth}px` }">
        <span
          v-for="(slot,index) in slots"
          :key="`${day}-${slot}-band`"
          class="interval-band"
          :class="`interval-${intervalKind(day,slot)}`"
          :style="{ left: `${index*cellWidth}px`, width: `${cellWidth}px` }"
          :title="intervalTitle(day,slot,index)"
        ></span>
        <span
          v-for="(tick,index) in ticks"
          :key="`${day}-${tick}`"
          class="time-tick"
          :class="{first:index===0,last:index===ticks.length-1}"
          :style="{ left: `${index*cellWidth}px` }"
        ><i></i><b>{{ tick }}</b></span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.timeline-header{background:#fafbfc}.day-row{display:grid}.day-cell{display:flex;height:43px;align-items:center;justify-content:center;gap:7px;border-right:2px solid #c8d1db;border-bottom:1px solid #e8ebef;color:#4a586c;font-size:12px}.day-cell span{color:#9aa3b1;font-size:10px}.day-cell em{border-radius:8px;background:#f9dede;padding:2px 6px;color:#a84f4f;font-size:8px;font-style:normal}.day-cell.day-holiday{background:#fff4f4}.day-cell.day-weekend{background:#f2f4f6;color:#8c96a3}.day-cell .workday-note{background:#e4f2ea;color:#43805f}.axis-row{display:flex;height:42px;border-bottom:1px solid #e8ebef}.time-axis{position:relative;flex:0 0 auto;border-right:2px solid #c8d1db}.interval-band{position:absolute;inset-block:0}.interval-off-hours{background:#e9edf1}.interval-holiday{background:#fde8e8}.time-tick{position:absolute;top:0;height:100%;transform:translateX(-50%);color:#7e8998;font-size:9px;white-space:nowrap}.time-tick i{position:absolute;top:20px;left:50%;width:1px;height:22px;background:#d8dee5}.time-tick b{display:block;font-weight:500}.time-tick.first{transform:none}.time-tick.first i{left:0}.time-tick.last{transform:translateX(-100%)}.time-tick.last i{right:0;left:auto}
</style>
