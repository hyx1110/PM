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

export interface NotificationPreference {
  id?: number
  user_id?: number
  in_app_enabled: boolean
  email_enabled: boolean
  wecom_enabled: boolean
  dingtalk_enabled: boolean
  upcoming_hours: number
}
