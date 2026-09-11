import { api } from './request'
import type { PageData } from '@/types/common'
import type { ImportJob } from '@/types/data-exchange'

export const downloadImportTemplate = (resource: string) => api.download(`/data-exchange/templates/${resource}`)
export const uploadImportWorkbook = (resource: string, file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post<ImportJob>(`/data-exchange/imports/${resource}`, form)
}
export const getImportJobs = (params: { page?: number; page_size?: number; resource_type?: string } = {}) =>
  api.get<PageData<ImportJob>>('/data-exchange/imports', { params })
export const downloadExport = (kind: 'schedules' | 'executions' | 'process-report', params: { start_date: string; end_date: string }) =>
  api.download(`/data-exchange/exports/${kind}`, { params })
