import type { PageQuery } from './common'

export interface Task {
  id: number
  project_id: number
  project_name?: string
  parent_id?: number
  name: string
  task_type: string
  owner_id: number
  owner_ids: number[]
  owner_names: string[]
  owner_name?: string
  project_manager_name?: string
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
  task_type: string
  owner_ids: number[]
  planned_start: string
  planned_end: string
  estimated_hours: number
  status: string
  description?: string
  remark?: string
}

export interface TaskQuery extends PageQuery {
  project_id?: number
  owner_id?: number
  status?: string
  department_id?: number
  organization_id?: number
  employee_no?: string
  name?: string
}
