import { api } from './request'
import type { PageData } from '@/types/common'
import type { Task, TaskPayload, TaskQuery } from '@/types/task'

export const getTasks = (params: TaskQuery = {}) => api.get<PageData<Task>>('/tasks', { params })
export async function getAllTasks(params: TaskQuery = {}) {
  const items: Task[] = []
  let page = 1
  let total = 0
  do {
    const result = await getTasks({ ...params, page, page_size: 200 })
    items.push(...result.items)
    total = result.total
    page += 1
    if (!result.items.length) break
  } while (items.length < total)
  return items
}
export const getMyTasks = (params: Pick<TaskQuery, 'page' | 'page_size' | 'status'> = {}) =>
  api.get<PageData<Task>>('/tasks/mine', { params })
export const getTask = (id: number) => api.get<Task>(`/tasks/${id}`)
export const createTask = (payload: TaskPayload) => api.post<Task>('/tasks', payload)
export const updateTask = (id: number, payload: Partial<TaskPayload>) => api.put<Task>(`/tasks/${id}`, payload)
export const deleteTask = (id: number) => api.delete<void>(`/tasks/${id}`)
