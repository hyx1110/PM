import { api } from './request'
import type { PageData } from '@/types/common'
import type { AppNotification, NotificationPreference } from '@/types/notification'

export const getNotifications = (params: { page?: number; page_size?: number; status?: string } = {}) =>
  api.get<PageData<AppNotification>>('/notifications', { params })
export const getUnreadCount = () => api.get<{ count: number }>('/notifications/unread-count')
export const markNotificationRead = (id: number) => api.post<AppNotification>(`/notifications/${id}/read`)
export const markAllNotificationsRead = () => api.post<{ updated: number }>('/notifications/read-all')
export const getNotificationPreference = () => api.get<NotificationPreference>('/notifications/preferences')
export const updateNotificationPreference = (payload: NotificationPreference) =>
  api.put<NotificationPreference>('/notifications/preferences', payload)
