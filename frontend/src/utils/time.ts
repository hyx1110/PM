import dayjs from 'dayjs'
import timezone from 'dayjs/plugin/timezone'
import utc from 'dayjs/plugin/utc'

dayjs.extend(utc)
dayjs.extend(timezone)

export const BEIJING_TIMEZONE = 'Asia/Shanghai'

export const beijingNow = () => dayjs().tz(BEIJING_TIMEZONE)
