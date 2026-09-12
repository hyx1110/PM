export interface WorkCalendarDay {
  id: number
  work_date: string
  day_type: 'holiday' | 'workday'
  name: string
  source?: string
  created_at: string
  updated_at: string
}

export interface WorkCalendarDayPayload {
  day_type: 'holiday' | 'workday'
  name: string
  source?: string
}

export interface ScheduleDayMeta {
  kind: 'workday' | 'holiday' | 'weekend'
  name?: string
}
