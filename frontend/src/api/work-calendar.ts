import { api } from './request'
import type { WorkCalendarDay, WorkCalendarDayPayload } from '@/types/work-calendar'

export const getWorkCalendar = (year: number) =>
  api.get<WorkCalendarDay[]>('/work-calendar', { params: { year } })
export const saveWorkCalendarDay = (date: string, payload: WorkCalendarDayPayload) =>
  api.put<WorkCalendarDay>(`/work-calendar/${date}`, payload)
export const deleteWorkCalendarDay = (date: string) =>
  api.delete<void>(`/work-calendar/${date}`)
