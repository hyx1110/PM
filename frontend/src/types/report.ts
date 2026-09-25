import type { PageQuery } from './common'

export interface ProcessReportItem {
  project_id: number
  project_name: string
  project_status: string
  level1_task?: string
  level2_task?: string
  task_path: string
  task_id: number
  parent_id?: number | null
  task_name: string
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
  evaluation_id?: number | null
  evaluated_at?: string | null
  effective_status: string
  task_status: string
  can_evaluate: boolean
}

export interface ProcessReportQuery extends PageQuery {
  project_id?: number
  owner_id?: number
  personnel_keyword?: string
  organization_keyword?: string
  personnel_scope?: string
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
  planned_hours_scope: string
  planned_hours_description: string
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
  recent_14_day_planned_hours: number
  monthly_planned_hours: number
  weekly_utilization_rate: number
  recent_14_day_utilization_rate: number
  task_completion_rate: number
  schedule_trend: Array<{ date: string; planned_hours: number }>
}

export interface WorkloadSummary {
  range: { start_date: string; end_date: string; granularity: string }
  periods: Array<{ period: string; planned_hours: number }>
  users: Array<{ user_id: number; user_name: string; planned_hours: number; available_hours: number; load_rate: number; load_status: 'idle' | 'normal' | 'overloaded' }>
  projects: Array<{ project_id: number; project_name: string; planned_hours: number; share: number }>
}

export type DashboardVariance = 'good' | 'warning' | 'severe'
export type DashboardHealthStatus = 'normal' | 'attention' | 'risk' | 'delayed'

export interface DashboardTaskItem {
  id: number
  project_id: number
  project_name: string
  parent_id?: number | null
  name: string
  owner_ids: number[]
  owner_name: string
  planned_start: string
  planned_end: string
  actual_start?: string | null
  actual_end?: string | null
  estimated_hours: number
  actual_hours: number
  planned_days: number
  actual_days: number
  deviation_hours: number
  deviation_rate: number
  variance: DashboardVariance
  status: string
  progress: number
  record_count: number
  description?: string | null
  remark?: string | null
}

export interface DashboardProjectTimelineItem {
  id: number
  code: string
  name: string
  manager_name: string
  planned_start: string
  planned_end: string
  actual_start?: string | null
  actual_end?: string | null
  status: string
  progress: number
  task_count: number
  completed_task_count: number
  tasks: DashboardTaskItem[]
}

export type DashboardPendingType = 'project_approval' | 'resource_approval' | 'booking'

export interface DashboardPendingItem {
  id: string
  source_id: number
  type: DashboardPendingType
  type_label: string
  title: string
  project_id: number
  project_name?: string | null
  task_id?: number
  applicant_name: string
  booking_user_name?: string
  content: string
  start_time?: string
  end_time?: string
  planned_hours?: number
  created_at?: string | null
  status: string
  actionable: boolean
}

export interface DashboardRiskAlert {
  id: string
  type: string
  severity: 'warning' | 'danger'
  title: string
  detail?: string | null
  project_id?: number | null
  project_name?: string | null
  task_id?: number | null
  task_name?: string | null
  occurred_at?: string | null
}

export interface DashboardProjectHealth {
  project_id: number
  project_name: string
  status: DashboardHealthStatus
  reason: string
  progress: number
}

export interface DashboardWorkbench {
  generated_at: string
  scope_label: string
  overview: {
    running_projects: number
    due_this_week: number
    task_completion_rate: number
    completed_tasks: number
    total_tasks: number
    pending_count: number
    pending_today: number
    pending_action_count: number
    pending_task_count: number
    risk_projects: number
    delayed_projects: number
    overrun_tasks: number
  }
  timeline: DashboardProjectTimelineItem[]
  execution_comparison: DashboardTaskItem[]
  pending_items: DashboardPendingItem[]
  my_tasks: DashboardTaskItem[]
  risk_alerts: DashboardRiskAlert[]
  workhour_trend: Array<{ date: string; planned_hours: number; actual_hours: number }>
  project_health: DashboardProjectHealth[]
}
