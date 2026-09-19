import type { PageQuery } from './common'

export interface Execution {
  id: number
  task_id: number
  task_name?: string
  project_id?: number
  project_name?: string
  user_id: number
  user_name?: string
  planned_start?: string
  planned_end?: string
  actual_start: string
  actual_end?: string
  actual_hours: number
  status: string
  description?: string
  exception_reason?: string
}

export interface ExecutionPayload {
  task_id: number
  user_id?: number
  actual_start: string
  actual_end?: string
  actual_hours?: number
  status: string
  description?: string
  exception_reason?: string
}

export interface ExecutionQuery extends PageQuery {
  task_id?: number
  user_id?: number
  project_id?: number
  start_date?: string
  end_date?: string
  mine?: boolean
  personnel_keyword?: string
  organization_keyword?: string
}
