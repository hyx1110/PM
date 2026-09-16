import type { PageQuery } from './common'

export interface ProcessReportItem {
  project_id: number
  project_name: string
  project_status: string
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
  task_status: string
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
  pending_project_approvals: number
  my_today_tasks: number
  my_upcoming_tasks: number
  today_schedules: number
  projects_completed: number
  projects_delayed: number
  open_risks: number
  critical_risks: number
  today_risks: number
  weekly_planned_hours: number
  monthly_planned_hours: number
  weekly_utilization_rate: number
  task_completion_rate: number
  schedule_trend: Array<{ date: string; planned_hours: number }>
}

export interface WorkloadSummary {
  range: { start_date: string; end_date: string; granularity: string }
  periods: Array<{ period: string; planned_hours: number }>
  users: Array<{ user_id: number; user_name: string; planned_hours: number; available_hours: number; load_rate: number; load_status: 'idle' | 'normal' | 'overloaded' }>
  projects: Array<{ project_id: number; project_name: string; planned_hours: number; share: number }>
}
