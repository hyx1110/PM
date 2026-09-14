import type { PageQuery } from './common'

export type ProjectApprovalStatus = 'draft' | 'pending' | 'approved' | 'rejected'

export interface Project {
  id: number
  code: string
  name: string
  project_type: string
  manager_id: number
  manager_name?: string
  department_id: number
  department_name?: string
  status: string
  planned_start: string
  planned_end: string
  actual_start?: string | null
  actual_end?: string | null
  priority: string
  description?: string | null
  remark?: string | null
  budget_hours: number
  booked_hours: number
  remaining_hours: number
  approval_status: ProjectApprovalStatus
  created_by?: number | null
  creator_name?: string | null
  approver_id?: number | null
  approval_required_name?: string | null
  approved_by?: number | null
  approver_name?: string | null
  approved_at?: string | null
  approval_note?: string | null
}

export interface ProjectPayload {
  code: string
  name: string
  project_type: string
  manager_id: number
  department_id: number
  budget_hours: number
  status: string
  planned_start: string
  planned_end: string
  actual_start?: string | null
  actual_end?: string | null
  priority: string
  description?: string
  remark?: string
}

export interface ProjectQuery extends PageQuery {
  keyword?: string
  status?: string
  manager_id?: number
  department_id?: number
  approval_status?: ProjectApprovalStatus
}

export interface ProjectMember {
  id: number
  project_id: number
  user_id: number
  user_name?: string
  project_role: string
  allocation_percent: number
  joined_at: string
  left_at?: string
}

export interface ProjectHourRequest {
  id: number
  project_id: number
  requested_hours: number
  reason: string
  status: 'pending' | 'approved' | 'rejected'
  requested_by: number
  requester_name?: string
  reviewed_by?: number
  reviewer_name?: string
  reviewed_at?: string
  review_note?: string
  created_at: string
  updated_at: string
}
