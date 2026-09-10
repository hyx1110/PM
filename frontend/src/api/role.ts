import { api } from './request'
import type { Permission, Role } from '@/types/role'

export const getRoles = () => api.get<Role[]>('/roles')
export const getPermissions = () => api.get<Permission[]>('/permissions')
export const updateRolePermissions = (id: number, permission_ids: number[]) =>
  api.put<Role>(`/roles/${id}/permissions`, { permission_ids })

