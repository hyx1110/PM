import type { PageQuery } from './common'

export type HRManagementLevel = 'employee' | 'department_manager' | 'management_manager'

export interface EmployeeProfilePayload {
  position_id?: string | null
  employee_type?: string | null
  local_f_name?: string | null
  english_f_name?: string | null
  local_g_name?: string | null
  english_g_name?: string | null
  preferred_name?: string | null
  gender?: string | null
  job_id?: string | null
  job_title?: string | null
  eng_job_title?: string | null
  chi_job_title?: string | null
  degree?: string | null
  staff_category?: string | null
  site?: string | null
  cost_center_code?: string | null
  personnel_area?: string | null
  personnel_sub_area?: string | null
  hr_management_level: HRManagementLevel
}

export interface EmployeeProfile extends EmployeeProfilePayload {
  id: number
  user_id: number
  data_source: 'local' | 'hrdb'
  synced_at?: string | null
  created_at: string
  updated_at: string
}

export interface User {
  id: number
  employee_no: string
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
  manual_role_ids: number[]
  hr_role_ids: number[]
  manual_roles: string[]
  hr_roles: string[]
  employee_profile?: EmployeeProfile | null
  created_at: string
  updated_at: string
}

export interface UserOption {
  id: number
  employee_no: string
  username: string
  name: string
  department_id?: number | null
  organization_id?: number | null
  supervisor_id?: number | null
}

export interface UserQuery extends PageQuery {
  keyword?: string
  department_id?: number
  status?: string
}

export interface UserPayload {
  employee_no?: string
  password?: string
  confirm_password?: string
  name: string
  email?: string
  phone?: string
  department_id?: number | null
  organization_id?: number | null
  supervisor_id?: number | null
  status: string
  role_ids?: number[]
  employee_profile?: EmployeeProfilePayload
}
