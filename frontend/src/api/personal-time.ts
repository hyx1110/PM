import { api } from './request'
import type { PageData } from '@/types/common'
import type {
  PersonalTimeBlock,
  PersonalTimePayload,
  PersonalTimeQuery,
} from '@/types/personal-time'

export const getPersonalTimeBlocks = (params: PersonalTimeQuery = {}) =>
  api.get<PageData<PersonalTimeBlock>>('/personal-time-blocks', { params })
export const getMyPersonalTimeBlocks = (
  params: Pick<PersonalTimeQuery, 'page' | 'page_size' | 'status'> = {},
) => api.get<PageData<PersonalTimeBlock>>('/personal-time-blocks/mine', { params })
export const createPersonalTimeBlock = (payload: PersonalTimePayload) =>
  api.post<PersonalTimeBlock>('/personal-time-blocks', payload)
export const withdrawPersonalTimeBlock = (id: number) =>
  api.post<PersonalTimeBlock>(`/personal-time-blocks/${id}/withdraw`)
