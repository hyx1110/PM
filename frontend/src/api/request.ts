import axios, { type AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import type { ApiResponse } from '@/types/common'

export const TOKEN_KEY = 'pm_access_token'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 20000,
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const responseData = error.response?.data as {
      message?: string
      data?: { errors?: Array<{ field?: string; message?: string }>; conflicts?: unknown[] }
    } | undefined
    const validationError = responseData?.data?.errors?.[0]
    const message = validationError?.message
      ? `${validationError.field || '参数'}：${validationError.message}`
      : responseData?.message || error.message || '请求失败'
    if (status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      if (window.location.pathname !== '/login') window.location.assign('/login')
    } else if (status !== 409 || !responseData?.data?.conflicts) {
      ElMessage.error(message)
    }
    return Promise.reject(error)
  },
)

async function unwrap<T>(request: Promise<{ data: ApiResponse<T> }>): Promise<T> {
  const response = await request
  if (response.data.code !== 0) throw new Error(response.data.message)
  return response.data.data
}

export const api = {
  get<T>(url: string, config?: AxiosRequestConfig) {
    return unwrap<T>(client.get(url, config))
  },
  post<T>(url: string, data?: unknown, config?: AxiosRequestConfig) {
    return unwrap<T>(client.post(url, data, config))
  },
  put<T>(url: string, data?: unknown, config?: AxiosRequestConfig) {
    return unwrap<T>(client.put(url, data, config))
  },
  delete<T>(url: string, config?: AxiosRequestConfig) {
    return unwrap<T>(client.delete(url, config))
  },
  async download(url: string, config?: AxiosRequestConfig) {
    const response = await client.get<Blob>(url, { ...config, responseType: 'blob' })
    return response.data
  },
}
