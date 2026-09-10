export interface Department {
  id: number
  code: string
  name: string
  manager_id?: number
  manager_name?: string
  status: string
}

export interface DepartmentOption {
  id: number
  code: string
  name: string
}

export interface OrganizationNode {
  id: number
  department_id: number
  parent_id?: number
  code: string
  name: string
  level: 'L1' | 'L2' | 'L3' | 'L4'
  manager_id?: number
  manager_name?: string
  status: string
  children: OrganizationNode[]
}
