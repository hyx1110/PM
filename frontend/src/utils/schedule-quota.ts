import dayjs from 'dayjs'
import type { Schedule } from '@/types/schedule'
import type { Task } from '@/types/task'
import { beijingNow } from '@/utils/time'

// Quota is reserved on submission, not on acceptance. Time conflicts still
// count accepted bookings only; do not use this helper for availability.
export function reservedBookingHours(booking?: Schedule): number {
  if (!booking) return 0
  const accepted = ['confirmed', 'running', 'completed'].includes(booking.status)
  const pending = ['pending', 'changed'].includes(booking.status)
    && dayjs(booking.end_time).format('YYYY-MM-DD HH:mm:ss') > beijingNow().format('YYYY-MM-DD HH:mm:ss')
  return accepted || pending ? Number(booking.planned_hours) : 0
}

export function remainingTaskHours(task?: Task, editing?: Schedule): number {
  if (!task) return 0
  const credit = editing?.task_id === task.id ? reservedBookingHours(editing) : 0
  return Math.max(0, Number(task.estimated_hours) - Number(task.booked_hours) + credit)
}

export function withinTaskDates(date: string, task?: Task): boolean {
  return Boolean(task && date && date >= task.planned_start.slice(0, 10) && date <= task.planned_end.slice(0, 10))
}
