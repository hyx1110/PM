import type { PageQuery } from './common'

export interface User {
  id: number
  username: string
  name: string
  email?: string | null
  phone?: string | null
  department_id?: number | null
  department_name?: string
  organization_id?: number | null
  organization_name?: string
  supervisor_id?: number | null
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
  department_id?: number | null
  organization_id?: number | null
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
  department_id?: number | null
  organization_id?: number | null
  supervisor_id?: number | null
  status: string
  role_ids?: number[]
}
