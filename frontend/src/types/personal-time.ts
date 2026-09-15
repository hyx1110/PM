import type { PageQuery } from './common'

export type PersonalTimeType = 'training' | 'meeting' | 'leave' | 'out_of_office' | 'business_trip' | 'other'

export interface PersonalTimeBlock {
  id: number
  user_id: number
  user_name?: string
  time_type: PersonalTimeType
  start_time: string
  end_time: string
  planned_hours: number
  status: 'active' | 'withdrawn'
  remark?: string
  withdrawn_at?: string
  created_at: string
  updated_at: string
}

export interface PersonalTimePayload {
  time_type: PersonalTimeType
  start_time: string
  end_time: string
  remark?: string
}

export interface PersonalTimeQuery extends PageQuery {
  start_date?: string
  end_date?: string
  user_id?: number
  status?: 'active' | 'withdrawn'
  sort_order?: 'asc' | 'desc'
}
