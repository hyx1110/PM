import { api } from './request'
import type { CurrentUser, LoginPayload, LoginResult, PasswordChangePayload, ProfileUpdatePayload } from '@/types/auth'

export const login = (payload: LoginPayload) => api.post<LoginResult>('/auth/login', payload)
export const getCurrentUser = () => api.get<CurrentUser>('/auth/me')
export const updateCurrentUser = (payload: ProfileUpdatePayload) => api.put<CurrentUser>('/auth/me', payload)
export const changeCurrentPassword = (payload: PasswordChangePayload) => api.put<void>('/auth/me/password', payload)
export const logout = () => api.post<void>('/auth/logout')
