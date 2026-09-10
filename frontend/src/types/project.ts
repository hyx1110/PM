import type { PageQuery } from './common'

export interface Project {
  id: number
  code: string
  name: string
  project_type: string
  manager_id: number
  manager_name?: string
  department_id?: number
  department_name?: string
  status: string
  planned_start: string
  planned_end: string
  actual_start?: string
  actual_end?: string
  priority: string
  description?: string
  remark?: string
}

export type ProjectPayload = Omit<Project, 'id' | 'manager_name' | 'department_name'>

export interface ProjectQuery extends PageQuery {
  keyword?: string
  status?: string
  manager_id?: number
  department_id?: number
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

