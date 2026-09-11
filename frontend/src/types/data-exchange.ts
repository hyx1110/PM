export interface ImportJob {
  id: number
  resource_type: string
  original_filename: string
  status: string
  total_rows: number
  success_rows: number
  failed_rows: number
  errors?: Array<{ row: number; field?: string; message: string }>
  operator_id: number
  operator_name?: string
  created_at: string
  updated_at: string
}
