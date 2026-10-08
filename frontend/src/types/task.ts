import type { PageQuery } from './common'

export interface Task {
  id: number
  project_id: number
  project_name?: string
  parent_id?: number
  name: string
  owner_id: number
  owner_ids: number[]
  owner_names: string[]
  owner_name?: string
  project_manager_name?: string
  project_manager_id: number
  can_manage: boolean
  can_edit: boolean
  can_delete: boolean
  can_review: boolean
  approval_status: 'pending' | 'approved' | 'rejected' | 'not_required'
  approval_note?: string | null
  approver_id?: number | null
  created_by?: number | null
  submitted_at?: string | null
  approved_by?: number | null
  approved_at?: string | null
  planned_start: string
  planned_end: string
  estimated_hours: number
  booked_hours: number
  status: string
  effective_status: string
  priority: string
  description?: string
  remark?: string
  children?: Task[]
}

export interface TaskPayload {
  project_id: number
  parent_id?: number
  name: string
  owner_ids: number[]
  planned_start: string
  planned_end: string
  estimated_hours: number
  description?: string
  remark?: string
}

export interface TaskQuery extends PageQuery {
  project_id?: number
  owner_id?: number
  status?: string
  approval_status?: string
  executable_only?: boolean
  department_id?: number
  organization_id?: number
  employee_no?: string
  name?: string
  managed_project_scope?: boolean
  personnel_keyword?: string
  organization_keyword?: string
  personnel_scope?: string
}
