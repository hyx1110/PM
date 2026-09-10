import { api } from './request'
import type { CurrentUser, LoginPayload, LoginResult } from '@/types/auth'

export const login = (payload: LoginPayload) => api.post<LoginResult>('/auth/login', payload)
export const getCurrentUser = () => api.get<CurrentUser>('/auth/me')
export const logout = () => api.post<void>('/auth/logout')

