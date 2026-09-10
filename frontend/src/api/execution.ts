import { api } from './request'
import type { PageData } from '@/types/common'
import type { Execution, ExecutionPayload, ExecutionQuery } from '@/types/execution'

export const getExecutions = (params: ExecutionQuery = {}) => api.get<PageData<Execution>>('/executions', { params })
export const getExecution = (id: number) => api.get<Execution>(`/executions/${id}`)
export const createExecution = (payload: ExecutionPayload) => api.post<Execution>('/executions', payload)
export const updateExecution = (id: number, payload: Partial<ExecutionPayload>) => api.put<Execution>(`/executions/${id}`, payload)

