export interface AppNotification {
  id: number
  recipient_id: number
  event_type: string
  title: string
  content: string
  level: string
  related_type?: string
  related_id?: string
  delivered_channels?: string[]
  status: 'unread' | 'read'
  read_at?: string
  created_at: string
}
