import dayjs from 'dayjs'

export const formatDate = (value?: string | null) => (value ? dayjs(value).format('YYYY-MM-DD') : '—')
export const formatDateTime = (value?: string | null) => (value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '—')
export const toApiDateTime = (value?: string | null) => (value ? dayjs(value).format('YYYY-MM-DD HH:mm:ss') : undefined)

