import type { PageQuery } from './common'

export interface Schedule {
  id: number
  user_id: number
  user_name?: string
  department_id?: number
  project_id: number
  project_name?: string
  task_id: number
  task_name?: string
  task_type?: string
  start_time: string
  end_time: string
  planned_hours: number
  status: string
  remark?: string
  rejection_reason?: string
  created_by: number
  has_conflict: boolean
}

export interface SchedulePayload {
  user_id: number
  project_id: number
  task_id: number
  start_time: string
  end_time: string
  planned_hours?: number
  remark?: string
}

export interface ScheduleQuery extends PageQuery {
  start_date?: string
  end_date?: string
  user_id?: number
  project_id?: number
  task_id?: number
  department_id?: number
  status?: string
}

export interface ScheduleConflict {
  schedule_id: number
  project_id: number
  project_name: string
  task_id: number
  task_name: string
  user_id: number
  user_name: string
  start_time: string
  end_time: string
}

