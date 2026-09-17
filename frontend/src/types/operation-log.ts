import type { PageQuery } from './common'

export interface OperationLog {
  id: number
  operator_id?: number
  operator_name?: string
  change_summary: string
  module: string
  action: string
  object_type: string
  object_id: string
  before_data?: Record<string, unknown>
  after_data?: Record<string, unknown>
  reason?: string
  ip_address?: string
  created_at: string
}

export interface OperationLogQuery extends PageQuery {
  operator_id?: number
  module?: string
  start_date?: string
  end_date?: string
}
