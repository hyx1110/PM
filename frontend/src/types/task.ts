import type { PageQuery } from './common'

export interface Task {
  id: number
  project_id: number
  project_name?: string
  parent_id?: number
  name: string
  task_type: string
  owner_id: number
  owner_name?: string
  planned_start: string
  planned_end: string
  estimated_hours: number
  status: string
  effective_status: string
  priority: string
  description?: string
  remark?: string
  children?: Task[]
}

export type TaskPayload = Omit<Task, 'id' | 'project_name' | 'owner_name' | 'effective_status' | 'children'>

export interface TaskQuery extends PageQuery {
  project_id?: number
  owner_id?: number
  status?: string
}

