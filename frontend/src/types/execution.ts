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
  estimated_hours: number
  task_actual_hours: number
  actual_start: string
  actual_end?: string
  actual_hours: number
  status: string
  description?: string
}

export interface ExecutionPayload {
  task_id: number
  user_id?: number
  actual_start: string
  actual_end?: string
  actual_hours?: number
  status: string
  description?: string
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
  personnel_scope?: string
}
