import { api } from './request'
import type { WorkCalendarDay, WorkCalendarDayPayload } from '@/types/work-calendar'

export interface PlannedHoursEstimate {
  workdays: number
  member_count: number
  hours_per_day: number
  planned_hours: number
}
export const getPlannedHours = (start_date: string, end_date: string, member_count: number) =>
  api.get<PlannedHoursEstimate>('/work-calendar/planned-hours', { params: { start_date, end_date, member_count } })

export const getWorkCalendar = (year: number) =>
  api.get<WorkCalendarDay[]>('/work-calendar', { params: { year } })
export const saveWorkCalendarDay = (date: string, payload: WorkCalendarDayPayload) =>
  api.put<WorkCalendarDay>(`/work-calendar/${date}`, payload)
export const deleteWorkCalendarDay = (date: string) =>
  api.delete<void>(`/work-calendar/${date}`)
