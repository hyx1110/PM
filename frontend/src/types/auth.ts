export interface CurrentUser {
  id: number
  employee_no: string
  username: string
  name: string
  email?: string
  department_id?: number
  organization_id?: number
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
