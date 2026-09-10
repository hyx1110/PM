export interface CurrentUser {
  id: number
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
  username: string
  password: string
}

export interface LoginResult {
  access_token: string
  token_type: string
  user: CurrentUser
}

