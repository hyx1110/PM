import { api } from './request'
import type { PageData, PageQuery } from '@/types/common'
import type { OvertimePayload, OvertimeRequest } from '@/types/overtime'

export const getOvertimeRequests = (params: PageQuery & { scope?: string; status?: string } = {}) => api.get<PageData<OvertimeRequest>>('/overtime', { params })
export const createOvertime = (payload: OvertimePayload) => api.post<OvertimeRequest>('/overtime', payload)
export const getOvertime = (id: number) => api.get<OvertimeRequest>(`/overtime/${id}`)
export const approveOvertime = (id: number, note?: string) => api.post<OvertimeRequest>(`/overtime/${id}/approve`, { note })
export const rejectOvertime = (id: number, note: string) => api.post<OvertimeRequest>(`/overtime/${id}/reject`, { note })
export const withdrawOvertime = (id: number) => api.post<OvertimeRequest>(`/overtime/${id}/withdraw`)
