import { api } from './request'
import type { PageData } from '@/types/common'
import type {
  DashboardSummary,
  EvaluationPayload,
  ProcessReportItem,
  ProcessReportQuery,
  WorkloadItem,
} from '@/types/report'

export const getProcessReport = (params: ProcessReportQuery = {}) =>
  api.get<PageData<ProcessReportItem>>('/reports/process', { params })
export const getWorkloadReport = (params: { start_date: string; end_date: string; department_id?: number; user_id?: number }) =>
  api.get<WorkloadItem[]>('/reports/workload', { params })
export const getEvaluation = (taskId: number) => api.get<EvaluationPayload | null>(`/tasks/${taskId}/evaluation`)
export const updateEvaluation = (taskId: number, payload: EvaluationPayload) =>
  api.put<EvaluationPayload>(`/tasks/${taskId}/evaluation`, payload)
export const getDashboardSummary = () => api.get<DashboardSummary>('/dashboard/summary')

