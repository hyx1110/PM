import type { PageQuery } from './common'

export interface RiskRecord {
  id: number
  fingerprint?: string
  risk_type: string
  risk_level: string
  title?: string
  project_id?: number
  project_name?: string
  task_id?: number
  task_name?: string
  user_id?: number
  user_name?: string
  status: string
  detail?: string
  source_data?: Record<string, unknown>
  detected_at: string
  due_at?: string
  handled_by?: number
  handler_name?: string
  handled_at?: string
  handling_note?: string
  resolved_at?: string
  created_at: string
  updated_at: string
}

export interface RiskQuery extends PageQuery {
  status?: string
  risk_type?: string
  risk_level?: string
  project_id?: number
  user_id?: number
}

export interface RiskStats {
  total: number
  open: number
  resolved: number
  by_status: Record<string, number>
  by_level: Record<string, number>
}
