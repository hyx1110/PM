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
