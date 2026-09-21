import { api } from './request'
import type { PageData } from '@/types/common'
import type { Project, ProjectMember, ProjectPayload, ProjectQuery, ProjectResourceRequest, ProjectResourceRequestPayload } from '@/types/project'

export const getProjects = (params: ProjectQuery = {}) => api.get<PageData<Project>>('/projects', { params })
export async function getAllProjects(params: ProjectQuery = {}) {
  const items: Project[] = []
  let page = 1
  let total = 0
  do {
    const result = await getProjects({ ...params, page, page_size: 200 })
    items.push(...result.items)
    total = result.total
    page += 1
    if (!result.items.length) break
  } while (items.length < total)
  return items
}
export const getProject = (id: number) => api.get<Project>(`/projects/${id}`)
export const createProject = (payload: ProjectPayload) => api.post<Project>('/projects', payload)
export const submitProject = (id: number) => api.post<Project>(`/projects/${id}/submit`)
export const completeProject = (id: number) => api.post<Project>(`/projects/${id}/complete`)
export const updateProject = (id: number, payload: Partial<ProjectPayload>) => api.put<Project>(`/projects/${id}`, payload)
export const deleteProject = (id: number) => api.delete<void>(`/projects/${id}`)
export const approveProject = (id: number, note?: string) =>
  api.post<Project>(`/projects/${id}/approve`, { note })
export const rejectProject = (id: number, note: string) =>
  api.post<Project>(`/projects/${id}/reject`, { note })
export const getProjectResourceRequests = (id: number) =>
  api.get<ProjectResourceRequest[]>(`/projects/${id}/resource-requests`)
export const getPendingProjectResourceRequests = () =>
  api.get<ProjectResourceRequest[]>('/projects/resource-requests/pending')
export const getPendingProjectApprovals = () =>
  api.get<Project[]>('/projects/approvals/pending')
export const createProjectResourceRequest = (id: number, payload: ProjectResourceRequestPayload) =>
  api.post<ProjectResourceRequest>(`/projects/${id}/resource-requests`, payload)
export const approveProjectResourceRequest = (projectId: number, requestId: number, note?: string) =>
  api.post<ProjectResourceRequest>(`/projects/${projectId}/resource-requests/${requestId}/approve`, { note })
export const rejectProjectResourceRequest = (projectId: number, requestId: number, note: string) =>
  api.post<ProjectResourceRequest>(`/projects/${projectId}/resource-requests/${requestId}/reject`, { note })
export const getProjectMembers = (id: number) => api.get<ProjectMember[]>(`/projects/${id}/members`)
