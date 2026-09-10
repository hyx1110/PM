<script setup lang="ts">
import dayjs from 'dayjs'

defineProps<{ days: string[]; hours: number[]; cellWidth: number }>()
</script>

<template>
  <div class="timeline-header" :style="{ width: `${days.length * hours.length * cellWidth}px` }">
    <div class="day-row" :style="{ gridTemplateColumns: `repeat(${days.length}, ${hours.length * cellWidth}px)` }">
      <div v-for="day in days" :key="day" class="day-cell"><strong>{{ dayjs(day).format('MM月DD日') }}</strong><span>{{ ['周日','周一','周二','周三','周四','周五','周六'][dayjs(day).day()] }}</span></div>
    </div>
    <div class="hour-row" :style="{ gridTemplateColumns: `repeat(${days.length * hours.length}, ${cellWidth}px)` }">
      <template v-for="day in days" :key="day"><div v-for="hour in hours" :key="`${day}-${hour}`" class="hour-cell">{{ String(hour).padStart(2,'0') }}:00</div></template>
    </div>
  </div>
</template>

<style scoped>
.timeline-header{background:#fafbfc}.day-row,.hour-row{display:grid}.day-cell{display:flex;height:37px;align-items:center;justify-content:center;gap:7px;border-right:1px solid #e4e8ed;border-bottom:1px solid #e8ebef;color:#4a586c;font-size:12px}.day-cell span{color:#9aa3b1;font-size:10px}.hour-cell{height:31px;border-right:1px solid #edf0f3;text-align:center;color:#99a2af;font-size:9px;line-height:31px}
</style>

