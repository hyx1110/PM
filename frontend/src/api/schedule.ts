import { api } from './request'
import type { PageData } from '@/types/common'
import type { Schedule, ScheduleBatchPayload, ScheduleCopyResult, ScheduleCopyWeekPayload, SchedulePayload, ScheduleQuery } from '@/types/schedule'

export const getSchedules = (params: ScheduleQuery = {}) => api.get<PageData<Schedule>>('/schedules', { params })
export const getSchedule = (id: number) => api.get<Schedule>(`/schedules/${id}`)
export const createSchedule = (payload: SchedulePayload) => api.post<Schedule>('/schedules', payload)
export const updateSchedule = (id: number, payload: Partial<SchedulePayload>) => api.put<Schedule>(`/schedules/${id}`, payload)
export const deleteSchedule = (id: number) => api.delete<void>(`/schedules/${id}`)
export const submitSchedule = (id: number) => api.post<Schedule>(`/schedules/${id}/submit`)
export const confirmSchedule = (id: number, reason?: string) => api.post<Schedule>(`/schedules/${id}/confirm`, { reason })
export const rejectSchedule = (id: number, reason?: string) => api.post<Schedule>(`/schedules/${id}/reject`, { reason })
export const moveSchedule = (id: number, payload: { start_time: string; end_time: string; expected_version: number }) =>
  api.post<Schedule>(`/schedules/${id}/move`, payload)
export const batchCreateSchedules = (payload: ScheduleBatchPayload) =>
  api.post<{ created: number; schedule_ids: number[] }>('/schedules/batch', payload)
export const copyScheduleWeek = (payload: ScheduleCopyWeekPayload) =>
  api.post<ScheduleCopyResult>('/schedules/copy-week', payload)
