import { api } from './request'
import type { PageData } from '@/types/common'
import type { Project, ProjectHourRequest, ProjectMember, ProjectPayload, ProjectQuery } from '@/types/project'

export const getProjects = (params: ProjectQuery = {}) => api.get<PageData<Project>>('/projects', { params })
export const getProject = (id: number) => api.get<Project>(`/projects/${id}`)
export const createProject = (payload: ProjectPayload) => api.post<Project>('/projects', payload)
export const submitProject = (id: number) => api.post<Project>(`/projects/${id}/submit`)
export const updateProject = (id: number, payload: Partial<ProjectPayload>) => api.put<Project>(`/projects/${id}`, payload)
export const deleteProject = (id: number) => api.delete<void>(`/projects/${id}`)
export const approveProject = (id: number, note?: string) =>
  api.post<Project>(`/projects/${id}/approve`, { note })
export const rejectProject = (id: number, note: string) =>
  api.post<Project>(`/projects/${id}/reject`, { note })
export const getProjectHourRequests = (id: number) =>
  api.get<ProjectHourRequest[]>(`/projects/${id}/hour-requests`)
export const createProjectHourRequest = (id: number, requestedHours: number, reason: string) =>
  api.post<ProjectHourRequest>(`/projects/${id}/hour-requests`, { requested_hours: requestedHours, reason })
export const approveProjectHourRequest = (projectId: number, requestId: number, note?: string) =>
  api.post<ProjectHourRequest>(`/projects/${projectId}/hour-requests/${requestId}/approve`, { note })
export const rejectProjectHourRequest = (projectId: number, requestId: number, note: string) =>
  api.post<ProjectHourRequest>(`/projects/${projectId}/hour-requests/${requestId}/reject`, { note })
export const getProjectMembers = (id: number) => api.get<ProjectMember[]>(`/projects/${id}/members`)
export const addProjectMember = (
  id: number,
  payload: Pick<ProjectMember, 'user_id' | 'project_role' | 'allocation_percent' | 'joined_at'>,
) => api.post<ProjectMember>(`/projects/${id}/members`, payload)
export const removeProjectMember = (id: number, userId: number) =>
  api.delete<void>(`/projects/${id}/members/${userId}`)
