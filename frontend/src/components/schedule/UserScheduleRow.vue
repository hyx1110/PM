<script setup lang="ts">
import { computed } from 'vue'
import dayjs from 'dayjs'
import type { Schedule } from '@/types/schedule'
import type { ScheduleDayMeta } from '@/types/work-calendar'

const props = defineProps<{
  userId: number
  userName: string
  days: string[]
  slots: string[]
  cellWidth: number
  schedules: Schedule[]
  currentUserId: number
  dayMeta: Record<string, ScheduleDayMeta>
}>()
const emit=defineEmits<{blank:[payload:{userId:number;date:string;time:string}];booking:[item:Schedule];dropBooking:[payload:{scheduleId:number;userId:number;date:string;time:string}]}>()
const gridWidth=computed(()=>props.days.length*props.slots.length*props.cellWidth)
const endTick=computed(()=>dayjs(`2000-01-01 ${props.slots.at(-1)||'17:30'}`).add(30,'minute').format('HH:mm'))
const visibleSchedules=computed(()=>props.schedules.filter(item=>item.user_id===props.userId).map(item=>{
  const date=dayjs(item.start_time).format('YYYY-MM-DD'),dayIndex=props.days.indexOf(date)
  if(dayIndex<0)return null
  const start=dayjs(item.start_time),end=dayjs(item.end_time)
  const slotIndex=props.slots.indexOf(start.format('HH:mm'))
  if(slotIndex<0)return null
  const durationSlots=Math.max(end.diff(start,'minute')/30,1)
  return {item,left:(dayIndex*props.slots.length+slotIndex)*props.cellWidth,width:Math.max(durationSlots*props.cellWidth-4,18)}
}).filter(Boolean) as Array<{item:Schedule;left:number;width:number}>)
const typeClass=(type?:string)=>`type-${(type||'Other').toLowerCase()}`
const canDrag=(item:Schedule)=>item.created_by===props.currentUserId&&['pending','rejected','confirmed'].includes(item.status)
const isWorkingSlot=(time:string)=>(time>='08:30'&&time<'12:00')||(time>='13:00'&&time<'17:30')
const slotKind=(date:string,time:string)=>props.dayMeta[date]?.kind==='holiday'?'holiday':props.dayMeta[date]?.kind==='weekend'?'off-hours':isWorkingSlot(time)?'work':'off-hours'
const isUnavailable=(date:string,time:string)=>slotKind(date,time)!=='work'
const intervalEnd=(index:number)=>index<props.slots.length-1?props.slots[index+1]:endTick.value
function slotTitle(date:string,time:string,index:number){const meta=props.dayMeta[date],end=intervalEnd(index);if(meta?.kind==='holiday')return `${date} ${meta.name||'法定节假日'}，不可预约`;if(meta?.kind==='weekend')return `${date} 周末休息，不可预约`;if(time>='12:00'&&time<'13:00')return `${date} ${time}–${end} 午休，不可预约`;if(!isWorkingSlot(time))return `${date} ${time}–${end} 非工作时间，不可预约`;return `${date} ${time}–${end}`}
function startDrag(event:DragEvent,item:Schedule){if(!canDrag(item))return event.preventDefault();event.dataTransfer?.setData('schedule-id',String(item.id));if(event.dataTransfer)event.dataTransfer.effectAllowed='move'}
function selectSlot(date:string,time:string){if(!isUnavailable(date,time))emit('blank',{userId:props.userId,date,time})}
function allowDrop(event:DragEvent,date:string,time:string){if(!isUnavailable(date,time))event.preventDefault()}
function dropBooking(event:DragEvent,date:string,time:string){if(isUnavailable(date,time))return;event.preventDefault();const scheduleId=Number(event.dataTransfer?.getData('schedule-id'));if(scheduleId)emit('dropBooking',{scheduleId,userId:props.userId,date,time})}
</script>

<template>
  <div class="schedule-row">
    <div class="person-cell"><span class="avatar">{{userName.slice(0,1)}}</span><strong>{{userName}}</strong></div>
    <div class="timeline" :style="{width:`${gridWidth}px`,gridTemplateColumns:`repeat(${days.length*slots.length},${cellWidth}px)`}">
      <template v-for="day in days" :key="day"><button v-for="(slot,index) in slots" :key="`${day}-${slot}`" class="slot" :class="`slot-${slotKind(day,slot)}`" :title="slotTitle(day,slot,index)" :disabled="isUnavailable(day,slot)" @click="selectSlot(day,slot)" @dragover="allowDrop($event,day,slot)" @drop="dropBooking($event,day,slot)"></button></template>
      <button v-for="entry in visibleSchedules" :key="entry.item.id" class="booking" :class="[typeClass(entry.item.task_type),{conflict:entry.item.has_conflict}]" :style="{left:`${entry.left+2}px`,width:`${entry.width}px`}" :title="`${entry.item.project_name} / ${entry.item.task_name}`" :draggable="canDrag(entry.item)" @dragstart="startDrag($event,entry.item)" @click.stop="emit('booking',entry.item)"><strong>{{entry.item.task_name}}</strong><span>{{dayjs(entry.item.start_time).format('HH:mm')}}–{{dayjs(entry.item.end_time).format('HH:mm')}}</span></button>
    </div>
  </div>
</template>

<style scoped>
.schedule-row{display:flex;min-height:62px;border-top:1px solid #edf0f3}.person-cell{position:sticky;left:0;z-index:5;display:flex;width:170px;flex:0 0 170px;align-items:center;gap:9px;border-right:1px solid #e2e6eb;background:#fff;padding:0 14px}.person-cell .avatar{display:grid;width:28px;height:28px;place-items:center;border-radius:9px;background:#eef2f6;color:#63758a;font-size:11px}.person-cell strong{overflow:hidden;color:#4a5668;font-size:12px;text-overflow:ellipsis;white-space:nowrap}.timeline{position:relative;display:grid;min-height:62px}.slot{border:0;border-right:1px solid #f0f2f5;background:transparent;cursor:crosshair}.slot:disabled{opacity:1}.slot-work:hover{background:#edf4fa}.slot-off-hours,.slot-off-hours:hover{background:#e9edf1;cursor:not-allowed}.slot-holiday,.slot-holiday:hover{background:#fde8e8;cursor:not-allowed}.booking{position:absolute;top:9px;z-index:2;display:flex;height:43px;flex-direction:column;justify-content:center;overflow:hidden;border:1px solid rgba(45,80,115,.15);border-radius:8px;background:#dfeaf4;padding:0 9px;text-align:left;color:#355878;cursor:pointer;box-shadow:0 3px 9px rgba(56,78,99,.08)}.booking strong,.booking span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.booking strong{font-size:11px}.booking span{margin-top:3px;font-size:9px;opacity:.75}.type-routine{background:#e4ece9;color:#48685c}.type-training{background:#eee9f3;color:#6d587f}.type-leave{background:#f3e9e8;color:#885d59}.type-other{background:#eceef1;color:#5f6976}.booking.conflict{border:2px solid #c75b5b;background:#f7dddd;color:#913e3e}
</style>
