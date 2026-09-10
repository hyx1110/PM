export interface Permission {
  id: number
  code: string
  name: string
  module: string
}

export interface Role {
  id: number
  code: string
  name: string
  description?: string
  is_system: boolean
  permission_ids: number[]
  permissions: string[]
}

