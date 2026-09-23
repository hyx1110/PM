<script setup lang="ts">
import { computed, ref } from 'vue'
import dayjs from 'dayjs'
import type { PersonalTimeBlock } from '@/types/personal-time'
import type { Schedule } from '@/types/schedule'
import type { ScheduleDayMeta } from '@/types/work-calendar'

const props = defineProps<{
  userId: number
  userName: string
  days: string[]
  slots: string[]
  cellWidth: number
  schedules: Schedule[]
  personalBlocks: PersonalTimeBlock[]
  currentUserId: number
  canManageAllSchedules: boolean
  draggingScheduleId?: number
  dayMeta: Record<string, ScheduleDayMeta>
}>()
const emit=defineEmits<{
  blank: [payload: { userId: number; date: string; time: string }]
  booking: [item: Schedule]
  personalBlock: [item: PersonalTimeBlock]
  person: [payload: { userId: number; userName: string }]
  dragStart: [scheduleId: number]
  dragEnd: []
  dropBlocked: [payload: { date: string; time: string }]
  dropError: []
  dropBooking: [payload: { scheduleId: number; userId: number; date: string; time: string }]
}>()
const localDraggingId=ref<number>()
const gridWidth=computed(()=>props.days.length*props.slots.length*props.cellWidth)
const endTick=computed(()=>dayjs(`2000-01-01 ${props.slots.at(-1)||'17:30'}`).add(30,'minute').format('HH:mm'))
const visibleSchedules=computed(()=>{
  const entries=props.schedules.filter(item=>item.user_id===props.userId).map(item=>{
  const date=dayjs(item.start_time).format('YYYY-MM-DD'),dayIndex=props.days.indexOf(date)
  if(dayIndex<0)return null
  const start=dayjs(item.start_time),end=dayjs(item.end_time)
  const slotIndex=props.slots.indexOf(start.format('HH:mm'))
  if(slotIndex<0)return null
  const durationSlots=Math.max(end.diff(start,'minute')/30,1)
  const left=(dayIndex*props.slots.length+slotIndex)*props.cellWidth
  return {item,left,width:Math.max(durationSlots*props.cellWidth-4,18),right:left+durationSlots*props.cellWidth,lane:0}
  }).filter(Boolean) as Array<{item:Schedule;left:number;width:number;right:number;lane:number}>
  const laneEnds:number[]=[]
  entries.sort((left,right)=>left.left-right.left||left.item.id-right.item.id).forEach((entry)=>{
    const availableLane=laneEnds.findIndex((end)=>end<=entry.left)
    entry.lane=availableLane<0?laneEnds.length:availableLane
    laneEnds[entry.lane]=entry.right
  })
  return entries
})
const scheduleLaneCount=computed(()=>Math.max(1,...visibleSchedules.value.map((entry)=>entry.lane+1)))
const rowHeight=computed(()=>Math.max(62,18+scheduleLaneCount.value*48))
const visiblePersonalBlocks=computed(()=>props.personalBlocks.filter(item=>item.user_id===props.userId&&item.status==='active').map(item=>{
  const date=dayjs(item.start_time).format('YYYY-MM-DD'),dayIndex=props.days.indexOf(date)
  if(dayIndex<0)return null
  const start=dayjs(item.start_time),end=dayjs(item.end_time)
  const slotIndex=props.slots.indexOf(start.format('HH:mm'))
  if(slotIndex<0)return null
  const durationSlots=Math.max(end.diff(start,'minute')/30,1)
  return {item,left:(dayIndex*props.slots.length+slotIndex)*props.cellWidth,width:Math.max(durationSlots*props.cellWidth-4,18)}
}).filter(Boolean) as Array<{item:PersonalTimeBlock;left:number;width:number}>)
const personalTypeLabel:Record<string,string>={training:'培训',meeting:'会议',leave:'休假',out_of_office:'外出',business_trip:'出差',other:'其他安排'}
const projectColors=[
  ['#dfeaf4','#355878','#9db9d2'],['#e4f1e8','#426b50','#a7cbb2'],
  ['#eee7f7','#694f85','#cbb8df'],['#f7edd9','#806238','#dfc48e'],
  ['#e3f0f7','#426b83','#a8c9dc'],['#f3e9e8','#885d59','#d8b5b1'],
]
function projectStyle(item:Schedule){
  if(['pending','changed'].includes(item.status))return {background:'#e7eaee',color:'#66717f',borderColor:'#cbd1d8'}
  const [background,color,borderColor]=projectColors[Math.abs(item.project_id)%projectColors.length]
  return {background,color,borderColor}
}
const movableStatuses=new Set(['pending','changed','rejected','confirmed'])
const canDrag=(item:Schedule)=>movableStatuses.has(item.status)&&(item.created_by===props.currentUserId||props.canManageAllSchedules)
const isWorkingSlot=(time:string)=>(time>='08:30'&&time<'12:00')||(time>='13:00'&&time<'17:30')
const slotKind=(date:string,time:string)=>props.dayMeta[date]?.kind==='holiday'?'holiday':props.dayMeta[date]?.kind==='weekend'?'off-hours':isWorkingSlot(time)?'work':'off-hours'
const isUnavailable=(date:string,time:string)=>slotKind(date,time)!=='work'
const intervalEnd=(index:number)=>index<props.slots.length-1?props.slots[index+1]:endTick.value
function slotTitle(date:string,time:string,index:number){const meta=props.dayMeta[date],end=intervalEnd(index);if(meta?.kind==='holiday')return `${date} ${meta.name||'法定节假日'}，不可预约`;if(meta?.kind==='weekend')return `${date} 周末休息，不可预约`;if(time>='12:00'&&time<'13:00')return `${date} ${time}–${end} 午休，不可预约`;if(!isWorkingSlot(time))return `${date} ${time}–${end} 非工作时间，不可预约`;return `${date} ${time}–${end}`}
function startDrag(event:DragEvent,item:Schedule){
  if(!canDrag(item))return event.preventDefault()
  localDraggingId.value=item.id
  event.dataTransfer?.setData('text/plain',String(item.id))
  event.dataTransfer?.setData('application/x-schedule-id',String(item.id))
  if(event.dataTransfer)event.dataTransfer.effectAllowed='move'
  emit('dragStart',item.id)
}
function endDrag(){localDraggingId.value=undefined;emit('dragEnd')}
function selectSlot(date:string,time:string){if(!isUnavailable(date,time))emit('blank',{userId:props.userId,date,time})}
function allowDrop(event:DragEvent,_date:string,_time:string){event.preventDefault();if(event.dataTransfer)event.dataTransfer.dropEffect='move'}
function dropBooking(event:DragEvent,date:string,time:string){
  event.preventDefault()
  if(isUnavailable(date,time)){emit('dropBlocked',{date,time});return}
  const rawId=event.dataTransfer?.getData('application/x-schedule-id')||event.dataTransfer?.getData('text/plain')
  const scheduleId=Number(rawId||props.draggingScheduleId||localDraggingId.value)
  if(!scheduleId){emit('dropError');return}
  emit('dropBooking',{scheduleId,userId:props.userId,date,time})
}
</script>

<template>
  <div class="schedule-row" :style="{minHeight:`${rowHeight}px`}">
    <button class="person-cell" title="查看该人员的全部项目时间安排" @click="emit('person',{userId,userName})">
      <span class="avatar">{{userName.slice(0,1)}}</span>
      <span class="person-info"><strong>{{userName}}</strong><small>查看全部安排 ›</small></span>
    </button>
    <div class="timeline" :style="{width:`${gridWidth}px`,minHeight:`${rowHeight}px`,gridTemplateColumns:`repeat(${days.length*slots.length},${cellWidth}px)`}">
      <template v-for="day in days" :key="day"><button v-for="(slot,index) in slots" :key="`${day}-${slot}`" class="slot" :class="[`slot-${slotKind(day,slot)}`,{'day-boundary':index===0,'drop-target':Boolean(localDraggingId)&&!isUnavailable(day,slot)}]" :title="slotTitle(day,slot,index)" :aria-disabled="isUnavailable(day,slot)" @click="selectSlot(day,slot)" @dragover="allowDrop($event,day,slot)" @drop="dropBooking($event,day,slot)"></button></template>
      <button v-for="entry in visibleSchedules" :key="entry.item.id" class="booking" :class="[`status-${entry.item.status}`,{conflict:entry.item.has_conflict,dragging:localDraggingId===entry.item.id,'can-drag':canDrag(entry.item)}]" :style="{left:`${entry.left+2}px`,top:`${9+entry.lane*48}px`,width:`${entry.width}px`,...projectStyle(entry.item)}" :title="canDrag(entry.item)?`${entry.item.project_name} / ${entry.item.task_name}；按住中间拖动改期`:`${entry.item.project_name} / ${entry.item.task_name}`" :draggable="canDrag(entry.item)" @dragstart="startDrag($event,entry.item)" @dragend="endDrag" @click.stop="emit('booking',entry.item)"><i v-if="canDrag(entry.item)" class="drag-handle" aria-hidden="true">⋮⋮</i><strong>{{entry.item.task_name}}</strong><span>{{dayjs(entry.item.start_time).format('HH:mm')}}–{{dayjs(entry.item.end_time).format('HH:mm')}}</span></button>
      <button v-for="entry in visiblePersonalBlocks" :key="`personal-${entry.item.id}`" class="booking personal-block" :class="`personal-${entry.item.time_type}`" :style="{left:`${entry.left+2}px`,width:`${entry.width}px`}" :title="`个人安排：${personalTypeLabel[entry.item.time_type]}${entry.item.remark?` / ${entry.item.remark}`:''}`" @click.stop="emit('personalBlock',entry.item)"><strong>{{personalTypeLabel[entry.item.time_type]}}</strong><span>{{dayjs(entry.item.start_time).format('HH:mm')}}–{{dayjs(entry.item.end_time).format('HH:mm')}}</span></button>
    </div>
  </div>
</template>

<style scoped>
.schedule-row{display:flex;min-height:62px;border-top:1px solid #edf0f3}.person-cell{position:sticky;left:0;z-index:5;display:flex;width:170px;flex:0 0 170px;align-items:center;gap:9px;border:0;border-right:1px solid #e2e6eb;background:#fff;padding:0 14px;text-align:left;cursor:pointer}.person-cell:hover{background:#f4f8fc}.person-cell:hover small{color:#315f8e}.person-cell:focus-visible{outline:2px solid #6b91b6;outline-offset:-2px}.person-cell .avatar{display:grid;width:28px;height:28px;flex:0 0 28px;place-items:center;border-radius:9px;background:#eef2f6;color:#63758a;font-size:11px}.person-info{display:flex;min-width:0;flex-direction:column}.person-cell strong,.person-cell small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.person-cell strong{color:#4a5668;font-size:12px}.person-cell small{margin-top:3px;color:#9aa5b3;font-size:9px}.timeline{position:relative;display:grid;min-height:62px}.slot{border:0;border-right:1px solid #f0f2f5;background:transparent;cursor:crosshair}.slot[aria-disabled="true"]{opacity:1}.slot-work:hover{background:#edf4fa}.slot-off-hours,.slot-off-hours:hover{background:#e9edf1;cursor:not-allowed}.slot-holiday,.slot-holiday:hover{background:#fde8e8;cursor:not-allowed}.booking{position:absolute;top:9px;z-index:2;display:flex;height:43px;flex-direction:column;justify-content:center;overflow:hidden;border:1px solid rgba(45,80,115,.15);border-radius:8px;background:#dfeaf4;padding:0 9px;text-align:left;color:#355878;cursor:pointer;box-shadow:0 3px 9px rgba(56,78,99,.08)}.booking strong,.booking span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.booking strong{font-size:11px}.booking span{margin-top:3px;font-size:9px;opacity:.75}.booking.conflict{border:2px solid #c75b5b;background:#f7dddd;color:#913e3e}.personal-block{z-index:3;border-width:1px;border-style:solid}.personal-training{border-color:#cfc2e2;background:#eee7f7;color:#694f85}.personal-meeting{border-color:#e3cfaa;background:#f7edd9;color:#806238}.personal-leave{border-color:#e5bcbc;background:#f9e2e2;color:#985353}.personal-out_of_office{border-color:#bdd4c4;background:#e4f1e8;color:#4f755a}.personal-business_trip{border-color:#b7cedf;background:#e3f0f7;color:#426b83}.personal-other{border-color:#cbd2d9;background:#e9edf1;color:#596573}
.slot.day-boundary{border-left:2px solid #c8d1db}.person-cell{border-right-width:2px;border-right-color:#c8d1db}
.booking.can-drag{cursor:grab}.booking.can-drag:active{cursor:grabbing}.booking.dragging{opacity:.45}.drag-handle{position:absolute;top:3px;right:5px;color:currentColor;font-size:9px;font-style:normal;letter-spacing:-2px;opacity:.55}
.slot.drop-target{box-shadow:inset 0 0 0 1px #8eafd0}.slot.drop-target:hover{background:#dfeaf4}
</style>
