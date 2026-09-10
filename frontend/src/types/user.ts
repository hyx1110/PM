import type { PageQuery } from './common'

export interface User {
  id: number
  username: string
  name: string
  email?: string
  phone?: string
  department_id?: number
  department_name?: string
  organization_id?: number
  organization_name?: string
  supervisor_id?: number
  supervisor_name?: string
  status: string
  roles: string[]
  role_ids: number[]
  created_at: string
  updated_at: string
}

export interface UserOption {
  id: number
  username: string
  name: string
  department_id?: number
  organization_id?: number
}

export interface UserQuery extends PageQuery {
  keyword?: string
  department_id?: number
  status?: string
}

export interface UserPayload {
  username?: string
  password?: string
  name: string
  email?: string
  phone?: string
  department_id?: number
  organization_id?: number
  supervisor_id?: number
  status: string
  role_ids?: number[]
}
