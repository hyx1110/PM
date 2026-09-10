import { api } from './request'
import type { PageData } from '@/types/common'
import type { OperationLog, OperationLogQuery } from '@/types/operation-log'

export const getOperationLogs = (params: OperationLogQuery = {}) =>
  api.get<PageData<OperationLog>>('/operation-logs', { params })

