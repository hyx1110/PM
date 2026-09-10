import { api } from './request'
import type { PageData } from '@/types/common'
import type { Project, ProjectMember, ProjectPayload, ProjectQuery } from '@/types/project'

export const getProjects = (params: ProjectQuery = {}) => api.get<PageData<Project>>('/projects', { params })
export const getProject = (id: number) => api.get<Project>(`/projects/${id}`)
export const createProject = (payload: ProjectPayload) => api.post<Project>('/projects', payload)
export const updateProject = (id: number, payload: Partial<ProjectPayload>) => api.put<Project>(`/projects/${id}`, payload)
export const deleteProject = (id: number) => api.delete<void>(`/projects/${id}`)
export const getProjectMembers = (id: number) => api.get<ProjectMember[]>(`/projects/${id}/members`)
export const addProjectMember = (
  id: number,
  payload: Pick<ProjectMember, 'user_id' | 'project_role' | 'allocation_percent' | 'joined_at'>,
) => api.post<ProjectMember>(`/projects/${id}/members`, payload)
export const removeProjectMember = (id: number, userId: number) =>
  api.delete<void>(`/projects/${id}/members/${userId}`)

