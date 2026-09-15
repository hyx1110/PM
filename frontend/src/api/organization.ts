import { api } from './request'
import type { Department, DepartmentOption, OrganizationNode } from '@/types/organization'

export const getDepartments = () => api.get<Department[]>('/departments')
export const createDepartment = (payload: Omit<Department, 'id' | 'data_source'>) => api.post<Department>('/departments', payload)
export const updateDepartment = (id: number, payload: Partial<Department>) => api.put<Department>(`/departments/${id}`, payload)
export const deleteDepartment = (id: number) => api.delete<void>(`/departments/${id}`)
export const getOrganizationTree = (department_id?: number) =>
  api.get<OrganizationNode[]>('/organizations/tree', { params: { department_id } })
export const createOrganization = (payload: Omit<OrganizationNode, 'id' | 'children' | 'data_source'>) =>
  api.post<OrganizationNode>('/organizations', payload)
export const updateOrganization = (id: number, payload: Partial<OrganizationNode>) =>
  api.put<OrganizationNode>(`/organizations/${id}`, payload)
export const deleteOrganization = (id: number) => api.delete<void>(`/organizations/${id}`)
export const getDepartmentOptions = () => api.get<DepartmentOption[]>('/lookups/departments')
