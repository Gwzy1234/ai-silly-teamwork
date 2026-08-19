import dayjs from 'dayjs'
import timezone from 'dayjs/plugin/timezone'
import utc from 'dayjs/plugin/utc'

dayjs.extend(utc)
dayjs.extend(timezone)

const NOTIFICATION_TIME_ZONE = 'Asia/Shanghai'
const UTC_DATE_TIME_PATTERN = /\b(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})(?::\d{2})?\s+UTC\b/g

function parseIsoDateTime(value: string) {
  const hasExplicitOffset = /(Z|[+-]\d{2}:?\d{2})$/i.test(value)
  return hasExplicitOffset ? dayjs(value) : dayjs.utc(value)
}

export function formatNotificationDateTime(
  value: string,
  format = 'YYYY-MM-DD HH:mm',
) {
  const parsed = parseIsoDateTime(value)
  return parsed.isValid() ? parsed.tz(NOTIFICATION_TIME_ZONE).format(format) : value
}

export function formatNotificationContent(content: string) {
  return content.replace(
    UTC_DATE_TIME_PATTERN,
    (_, date: string, time: string) =>
      `${formatNotificationDateTime(`${date}T${time}:00Z`)}（北京时间）`,
  )
}
