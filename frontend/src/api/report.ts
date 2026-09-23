import { api } from './request'
import type { PageData } from '@/types/common'
import type {
  DashboardSummary,
  EvaluationPayload,
  ProcessReportItem,
  ProcessReportQuery,
  WorkloadItem,
  WorkloadSummary,
} from '@/types/report'

export const getProcessReport = (params: ProcessReportQuery = {}) =>
  api.get<PageData<ProcessReportItem>>('/reports/process', { params })
export const getWorkloadReport = (params: { start_date: string; end_date: string; department_id?: number; user_id?: number }) =>
  api.get<WorkloadItem[]>('/reports/workload', { params })
export const getEvaluation = (projectId: number) => api.get<EvaluationPayload | null>(`/projects/${projectId}/evaluation`)
export const updateEvaluation = (projectId: number, payload: EvaluationPayload) =>
  api.put<EvaluationPayload>(`/projects/${projectId}/evaluation`, payload)
export const getDashboardSummary = () => api.get<DashboardSummary>('/dashboard/summary')
export const getWorkloadSummary = (params: { start_date: string; end_date: string; granularity: string }) =>
  api.get<WorkloadSummary>('/reports/workload-summary', { params })
