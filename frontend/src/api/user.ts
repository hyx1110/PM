import { api } from './request'
import type { PageData } from '@/types/common'
import type { User, UserOption, UserPayload, UserQuery } from '@/types/user'

export const getUsers = (params: UserQuery) => api.get<PageData<User>>('/users', { params })
export const getUser = (id: number) => api.get<User>(`/users/${id}`)
export const createUser = (payload: UserPayload) => api.post<User>('/users', payload)
export const updateUser = (id: number, payload: Partial<UserPayload>) => api.put<User>(`/users/${id}`, payload)
export const deleteUser = (id: number) => api.delete<void>(`/users/${id}`)
export const assignUserRoles = (id: number, role_ids: number[]) => api.put<User>(`/users/${id}/roles`, { role_ids })
export const getUserOptions = () => api.get<UserOption[]>('/lookups/users')
export const getL3UserOptions = () => api.get<UserOption[]>('/lookups/l3-users')
export const getScheduleUserOptions = (params: { project_id?: number; keyword?: string; department_id?: number; organization_id?: number } = {}) =>
  api.get<UserOption[]>('/lookups/schedule-users', { params })
export const getScheduleProjectOptions = () =>
  api.get<Array<{ id: number; code: string; name: string }>>('/lookups/schedule-projects')
