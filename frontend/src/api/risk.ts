import { api } from './request'
import type { PageData } from '@/types/common'
import type { RiskQuery, RiskRecord, RiskStats } from '@/types/risk'

export const getRisks = (params: RiskQuery = {}) => api.get<PageData<RiskRecord>>('/risks', { params })
export const getRiskStats = () => api.get<RiskStats>('/risks/stats')
export const syncRisks = () => api.post<{ detected: number; created: number; refreshed: number; reopened: number }>('/risks/sync')
export const handleRisk = (id: number, payload: { status: string; handling_note: string }) =>
  api.post<{ id: number; status: string; updated: boolean }>(`/risks/${id}/handle`, payload)
