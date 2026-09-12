import { api } from './request'
import type { PageData } from '@/types/common'
import type { Task, TaskPayload, TaskQuery } from '@/types/task'

export const getTasks = (params: TaskQuery = {}) => api.get<PageData<Task>>('/tasks', { params })
export const getTask = (id: number) => api.get<Task>(`/tasks/${id}`)
export const createTask = (payload: TaskPayload) => api.post<Task>('/tasks', payload)
export const updateTask = (id: number, payload: Partial<TaskPayload>) => api.put<Task>(`/tasks/${id}`, payload)
export const deleteTask = (id: number) => api.delete<void>(`/tasks/${id}`)
