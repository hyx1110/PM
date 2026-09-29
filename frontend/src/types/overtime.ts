export type OvertimeStatus = 'pending' | 'approved' | 'rejected' | 'withdrawn'
export interface OvertimeRequest {
  id: number
  project_id: number
  project_name: string
  task_id: number
  task_name: string
  user_id: number
  user_name: string
  approver_id: number
  approver_name: string
  start_time: string
  end_time: string
  hours: number | string
  reason: string
  status: OvertimeStatus
  created_at: string
  reviewed_at?: string
  review_note?: string
  execution_id?: number
  can_review: boolean
  can_withdraw: boolean
  can_record: boolean
}
export interface OvertimePayload {
  task_id: number
  start_time: string
  end_time: string
  reason: string
}
