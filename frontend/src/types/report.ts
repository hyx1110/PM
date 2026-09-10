import type { PageQuery } from './common'

export interface ProcessReportItem {
  project_id: number
  project_name: string
  level1_task?: string
  level2_task?: string
  task_id: number
  owner_id: number
  owner_name: string
  planned_start: string
  planned_end: string
  actual_start?: string
  actual_end?: string
  estimated_hours: number
  actual_hours: number
  achievement_rate?: number
  achievement_quality?: number
  effective_status: string
}

export interface ProcessReportQuery extends PageQuery {
  project_id?: number
  owner_id?: number
  start_date?: string
  end_date?: string
}

export interface EvaluationPayload {
  achievement_rate: number
  achievement_quality: number
  comment?: string
}

export interface WorkloadItem {
  user_id: number
  user_name: string
  date: string
  planned_hours: number
  available_hours: number
  load_rate: number
  overloaded: boolean
}

export interface DashboardSummary {
  projects_total: number
  projects_running: number
  delayed_tasks: number
  pending_schedules: number
  today_schedules: number
}

