export interface Department {
  id: number
  code: string
  name: string
  manager_id?: number | null
  manager_name?: string | null
  status: string
  data_source: 'local' | 'hrdb'
}

export interface DepartmentOption {
  id: number
  code: string
  name: string
  manager_id?: number | null
}

export interface OrganizationNode {
  id: number
  department_id: number
  parent_id?: number | null
  code: string
  name: string
  level: 'L1' | 'L2' | 'L3' | 'L4'
  manager_id?: number | null
  manager_name?: string | null
  status: string
  data_source: 'local' | 'hrdb'
  users: Array<{ id: number; employee_no: string; name: string; status: string }>
  children: OrganizationNode[]
}
