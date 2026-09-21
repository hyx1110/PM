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
  start_time: string
  end_time: string
  planned_hours: number
  status: string
  remark?: string
  rejection_reason?: string
  created_by: number
  created_by_name?: string
  source_booking_id?: number
  version: number
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
  sort_order?: 'asc' | 'desc'
}

export interface ScheduleConflict {
  conflict_type: 'project_booking' | 'personal_time'
  conflict_id: number
  schedule_id?: number
  personal_time_id?: number
  project_id?: number
  project_name: string
  task_id?: number
  task_name: string
  personal_time_type?: string
  user_id: number
  user_name: string
  start_time: string
  end_time: string
}

export interface ScheduleBatchPayload {
  user_ids: number[]
  project_id: number
  task_id: number
  start_time: string
  end_time: string
  planned_hours?: number
  remark?: string
}
