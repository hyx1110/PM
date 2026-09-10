<script setup lang="ts">
import { computed } from 'vue'
import dayjs from 'dayjs'
import type { Schedule } from '@/types/schedule'

const props=defineProps<{userId:number;userName:string;days:string[];hours:number[];cellWidth:number;schedules:Schedule[]}>()
const emit=defineEmits<{blank:[payload:{userId:number;date:string;hour:number}];booking:[item:Schedule]}>()
const gridWidth=computed(()=>props.days.length*props.hours.length*props.cellWidth)
const visibleSchedules=computed(()=>props.schedules.filter(item=>item.user_id===props.userId).map(item=>{
  const date=dayjs(item.start_time).format('YYYY-MM-DD'),dayIndex=props.days.indexOf(date)
  if(dayIndex<0)return null
  const firstHour=props.hours[0],lastHour=props.hours[props.hours.length-1]+1
  const start=dayjs(item.start_time),end=dayjs(item.end_time)
  const windowStart=dayjs(date).hour(firstHour).minute(0).second(0),windowEnd=dayjs(date).hour(lastHour).minute(0).second(0)
  if(end<=windowStart||start>=windowEnd)return null
  const clippedStart=start<windowStart?windowStart:start,clippedEnd=end>windowEnd?windowEnd:end
  const offsetHours=clippedStart.diff(windowStart,'minute')/60,duration=Math.max(clippedEnd.diff(clippedStart,'minute')/60,.25)
  return {item,left:(dayIndex*props.hours.length+offsetHours)*props.cellWidth,width:Math.max(duration*props.cellWidth-4,18)}
}).filter(Boolean) as Array<{item:Schedule;left:number;width:number}>)
const typeClass=(type?:string)=>`type-${(type||'Other').toLowerCase()}`
</script>

<template>
  <div class="schedule-row">
    <div class="person-cell"><span class="avatar">{{userName.slice(0,1)}}</span><strong>{{userName}}</strong></div>
    <div class="timeline" :style="{width:`${gridWidth}px`,gridTemplateColumns:`repeat(${days.length*hours.length},${cellWidth}px)`}">
      <template v-for="day in days" :key="day"><button v-for="hour in hours" :key="`${day}-${hour}`" class="slot" :title="`${day} ${hour}:00`" @click="emit('blank',{userId,date:day,hour})"></button></template>
      <button v-for="entry in visibleSchedules" :key="entry.item.id" class="booking" :class="[typeClass(entry.item.task_type),{conflict:entry.item.has_conflict}]" :style="{left:`${entry.left+2}px`,width:`${entry.width}px`}" :title="`${entry.item.project_name} / ${entry.item.task_name}`" @click.stop="emit('booking',entry.item)"><strong>{{entry.item.task_name}}</strong><span>{{dayjs(entry.item.start_time).format('HH:mm')}}–{{dayjs(entry.item.end_time).format('HH:mm')}}</span></button>
    </div>
  </div>
</template>

<style scoped>
.schedule-row{display:flex;min-height:62px;border-top:1px solid #edf0f3}.person-cell{position:sticky;left:0;z-index:5;display:flex;width:170px;flex:0 0 170px;align-items:center;gap:9px;border-right:1px solid #e2e6eb;background:#fff;padding:0 14px}.person-cell .avatar{display:grid;width:28px;height:28px;place-items:center;border-radius:9px;background:#eef2f6;color:#63758a;font-size:11px}.person-cell strong{overflow:hidden;color:#4a5668;font-size:12px;text-overflow:ellipsis;white-space:nowrap}.timeline{position:relative;display:grid;min-height:62px}.slot{border:0;border-right:1px solid #f0f2f5;background:transparent;cursor:crosshair}.slot:hover{background:#edf4fa}.booking{position:absolute;top:9px;z-index:2;display:flex;height:43px;flex-direction:column;justify-content:center;overflow:hidden;border:1px solid rgba(45,80,115,.15);border-radius:8px;background:#dfeaf4;padding:0 9px;text-align:left;color:#355878;cursor:pointer;box-shadow:0 3px 9px rgba(56,78,99,.08)}.booking strong,.booking span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.booking strong{font-size:11px}.booking span{margin-top:3px;font-size:9px;opacity:.75}.type-routine{background:#e4ece9;color:#48685c}.type-training{background:#eee9f3;color:#6d587f}.type-leave{background:#f3e9e8;color:#885d59}.type-other{background:#eceef1;color:#5f6976}.booking.conflict{border:2px solid #c75b5b;background:#f7dddd;color:#913e3e}
</style>

