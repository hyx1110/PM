export interface CurrentUser {
  id: number
  employee_no: string
  name: string
  email?: string | null
  department_id?: number | null
  organization_id?: number | null
  supervisor_id?: number | null
  status: string
  roles: string[]
  permissions: string[]
}

export interface LoginPayload {
  employee_no: string
  password: string
}

export interface LoginResult {
  access_token: string
  token_type: string
  user: CurrentUser
}
